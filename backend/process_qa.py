import os
import glob
from collections import OrderedDict
from typing import Any
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, PDFPlumberLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain_google_genai import GoogleGenerativeAIEmbeddings  # Add Google embeddings
from langchain_google_genai import ChatGoogleGenerativeAI  # Add Google chat
from langchain_community.vectorstores import FAISS
from langchain.schema import StrOutputParser
from langchain.prompts import ChatPromptTemplate
import pypdf
import io
# Import OCR libraries
import pytesseract
from pdf2image import convert_from_path
import tempfile
from langchain_huggingface import HuggingFaceEmbeddings

# Load environment variables
load_dotenv()

# Get and check Google API key instead of OpenAI
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable is not set. Please set it in your .env file.")

# Print first few characters to verify key format without exposing the full key
print(f"Using Google API key starting with: {GOOGLE_API_KEY[:5]}...")

# Define paths
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_pdfs")
VECTOR_STORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vector_store")

# Create vector store directory if it doesn't exist
os.makedirs(VECTOR_STORE_PATH, exist_ok=True)

# Maximum number of vector stores to keep in memory simultaneously
MAX_CACHE_SIZE = 5

class LRUCache(OrderedDict):
    """Limited size dictionary that removes the least recently used items."""

    def __init__(self, capacity):
        super().__init__()
        self.capacity = capacity

    def get(self, key):
        if key not in self:
            return None
        self.move_to_end(key)
        return self[key]

    def put(self, key, value):
        if key in self:
            self.move_to_end(key)
        self[key] = value
        if len(self) > self.capacity:
            # Remove the first item (least recently used)
            self.popitem(last=False)


class PDFProcessor:
    def __init__(self):
        try:
            self.embeddings = HuggingFaceEmbeddings(
                                     model_name="sentence-transformers/all-MiniLM-L6-v2"
                                     )
            self.vector_store = None
            
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-pro-exp-03-25", 
                temperature=0
            )
            self.company_vector_stores = LRUCache(MAX_CACHE_SIZE)
            self.download_path = DOWNLOAD_FOLDER
        except Exception as e:
            print(f"Error initializing Google AI services: {e}")
            import traceback
            traceback.print_exc()
            raise

    def get_company_vector_store_path(self, company_number):
        """Get the path for a company-specific vector store."""
        return os.path.join(VECTOR_STORE_PATH, str(company_number))

    def load_and_process_pdfs(self, specific_company=None):
        """
        Process PDFs for a specific company into a vector store.
        Company number is required and only PDFs for that specific company will be processed.
        """
        if not specific_company:
            print("Company code is required for processing PDFs.")
            return False

        company_path = os.path.join(DOWNLOAD_FOLDER, str(specific_company))
        if not os.path.isdir(company_path):
            print(f"Directory for company {specific_company} not found at {company_path}")
            return False

        company_pdfs = glob.glob(os.path.join(company_path, "*.pdf"))

        if not company_pdfs:
            print(f"No PDF files found for company {specific_company}.")
            return False

        # Process this company's PDFs
        success = self._process_company_pdfs(specific_company)

        if success:
            # Use this company's vector store as the active one
            self.vector_store = self.company_vector_stores.get(specific_company)

        return success

    def _load_pdf_with_fallbacks(self, pdf_file):
        """
        Try to load a PDF with multiple methods, falling back to alternatives if one fails.
        Returns a list of documents or an empty list if all methods fail.
        """
        print(f"Attempting to load PDF: {pdf_file}")
        
        documents = []
        
        # Try method 1: PyPDFLoader (fastest but less robust)
        try:
            print(f"  Trying PyPDFLoader...")
            loader = PyPDFLoader(pdf_file)
            documents = loader.load()
            
            # Check if documents contain actual text
            has_text = False
            for doc in documents:
                if doc.page_content and doc.page_content.strip():
                    has_text = True
                    break
                
            if has_text:
                print(f"  Successfully loaded PDF with PyPDFLoader: {len(documents)} pages")
                return documents
            else:
                print(f"  PyPDFLoader loaded {len(documents)} pages but no text content was found")
        except Exception as e:
            print(f"  Error with PyPDFLoader: {e}")
        
        # Try method 2: PDFPlumberLoader (more robust)
        try:
            print(f"  Trying PDFPlumberLoader...")
            loader = PDFPlumberLoader(pdf_file)
            documents = loader.load()
            
            # Check if documents contain actual text
            has_text = False
            for doc in documents:
                if doc.page_content and doc.page_content.strip():
                    has_text = True
                    break
                
            if has_text:
                print(f"  Successfully loaded PDF with PDFPlumberLoader: {len(documents)} pages")
                return documents
            else:
                print(f"  PDFPlumberLoader loaded {len(documents)} pages but no text content was found")
        except Exception as e:
            print(f"  Error with PDFPlumberLoader: {e}")
            
        # Try method 3: Direct PyPDF approach with error recovery
        try:
            print(f"  Trying direct PyPDF approach...")
            reader = pypdf.PdfReader(pdf_file, strict=False)
            text_content = []
            
            for i, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    if text.strip():  # If page has text
                        text_content.append({
                            "page_content": text,
                            "metadata": {
                                "source": pdf_file,
                                "page": i
                            }
                        })
                except Exception as page_e:
                    print(f"    Error extracting text from page {i}: {page_e}")
            
            if text_content:
                print(f"  Successfully extracted text from {len(text_content)} pages with PyPDF")
                from langchain_core.documents import Document
                documents = [Document(page_content=item["page_content"], metadata=item["metadata"]) for item in text_content]
                return documents
            else:
                print(f"  No text content found with direct PyPDF approach")
        except Exception as e:
            print(f"  Error with direct PyPDF approach: {e}")
        
        # Try method 4: OCR using pytesseract and pdf2image
        try:
            print(f"  Trying OCR with pytesseract...")
            
            # Create a temporary directory to store images
            with tempfile.TemporaryDirectory() as temp_dir:
                # Convert PDF to images
                print(f"    Converting PDF pages to images...")
                images = convert_from_path(pdf_file)
                print(f"    Converted {len(images)} pages to images")
                
                text_content = []
                
                # Process each page
                for i, image in enumerate(images):
                    try:
                        # Extract text using OCR
                        text = pytesseract.image_to_string(image)
                        
                        if text.strip():  # If page has text
                            text_content.append({
                                "page_content": text,
                                "metadata": {
                                    "source": pdf_file,
                                    "page": i
                                }
                            })
                    except Exception as page_e:
                        print(f"    Error extracting text from image {i}: {page_e}")
                
                if text_content:
                    print(f"  Successfully extracted text from {len(text_content)} pages with OCR")
                    from langchain_core.documents import Document
                    documents = [Document(page_content=item["page_content"], metadata=item["metadata"]) for item in text_content]
                    return documents
                else:
                    print(f"  No text content found with OCR")
        except Exception as e:
            print(f"  Error with OCR approach: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"  Could not extract text from PDF with any method, including OCR")
        return []

    def _process_company_pdfs(self, company_number):
        """Process PDFs for a specific company and create a vector store."""
        if not company_number:
            print("Company number is required.")
            return False

        company_path = os.path.join(DOWNLOAD_FOLDER, str(company_number))
        company_pdfs = glob.glob(os.path.join(company_path, "*.pdf"))

        if not company_pdfs:
            print(f"No PDFs found for company {company_number}")
            return False

        documents = []

        for pdf_file in company_pdfs:
            try:
                # Use our robust PDF loading method
                pdf_documents = self._load_pdf_with_fallbacks(pdf_file)
                
                # Add metadata to each page
                for doc in pdf_documents:
                    doc.metadata["company_number"] = company_number

                documents.extend(pdf_documents)
            except Exception as e:
                print(f"Error processing {pdf_file}: {e}")

        if not documents:
            print(f"No documents were successfully loaded for company {company_number}")
            print("This might be because the PDFs are scanned images without text or are corrupted.")
            print("Consider using OCR tools to extract text from these PDFs if they contain valuable information.")
            return False

        # Add additional check for empty documents
        non_empty_documents = []
        for doc in documents:
            if doc.page_content and doc.page_content.strip():
                non_empty_documents.append(doc)
            else:
                print(f"Skipping empty document from {doc.metadata.get('source', 'unknown source')}")
                
        if not non_empty_documents:
            print(f"All documents loaded for company {company_number} contain no extractable text.")
            print("This suggests the PDFs might be scanned images without OCR processing.")
            return False
            
        documents = non_empty_documents

        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )

        chunks = text_splitter.split_documents(documents)
        
        # Check if chunks is empty
        if not chunks:
            print(f"No text chunks were created for company {company_number}. The documents might be empty or unprocessable.")
            return False
            
        # Debug information
        print(f"Created {len(chunks)} text chunks for processing")
        
        try:
            # Create vector store for this company
            print("Creating FAISS vector store...")
            company_vector_store = FAISS.from_documents(chunks, self.embeddings)
            
            # Save the company vector store
            company_vector_store_path = self.get_company_vector_store_path(company_number)
            os.makedirs(company_vector_store_path, exist_ok=True)
            company_vector_store.save_local(company_vector_store_path)
            
            self.company_vector_stores.put(company_number, company_vector_store)
            
            print(f"Successfully created and saved vector store for company {company_number}")
            return True
            
        except Exception as e:
            print(f"Error creating embeddings or vector store: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_vector_store(self, company_number):
        """Update the vector store for a specific company with new PDFs."""
        if not company_number:
            print("Company number is required to update vector store.")
            return False

        success = self._process_company_pdfs(company_number)

        if success:
            # The company's vector store is now in the cache
            self.vector_store = self.company_vector_stores.get(company_number)
            return True

        return False

    def load_vector_store(self, company_number):
        """
        Load a specific company's vector store.
        Company number is required.
        """
        if not company_number:
            print("Company number is required to load vector store.")
            return False

        # First check if it's already in the cache
        cached_vs = self.company_vector_stores.get(company_number)
        if cached_vs:
            print(f"Using cached vector store for company {company_number}")
            self.vector_store = cached_vs
            return True

        # If not in cache, load from disk
        company_path = self.get_company_vector_store_path(company_number)
        if os.path.exists(company_path):
            try:
                vector_store = FAISS.load_local(
                    company_path, 
                    self.embeddings, 
                    allow_dangerous_deserialization=True
                )

                # Add to cache
                self.company_vector_stores.put(company_number, vector_store)
                self.vector_store = vector_store

                return True
            except Exception as e:
                print(f"Error loading vector store for company {company_number}: {e}")
                return False
        else:
            print(f"No vector store found for company {company_number}")
            return False

    def setup_qa_chain(self):
        """Set up a question-answering chain."""
        if not self.vector_store:
            raise ValueError("Vector store not loaded. Call load_vector_store() or load_and_process_pdfs() first.")

        retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 4}  # Retrieve top 4 most relevant chunks
        )

        template = """You are an AI assistant that helps answer questions based on PDF documents.
        
        Use the following context to answer the question. If you don't know the answer from the provided context, say you don't know.
        
        Context:
        {context}
        
        Question: {question}
        """

        prompt = ChatPromptTemplate.from_template(template)

        qa_chain = (
                {"context": retriever, "question": lambda x: x}
                | prompt
                | self.llm
                | StrOutputParser()
        )

        return qa_chain

    def answer_question(self, question, company_number):
        """
        Answer a question using the QA chain for a specific company.
        Company number is required.
        """
        if not company_number:
            return "Please specify a company number to ask questions about."

        # First try to get vector store from cache
        cached_vs = self.company_vector_stores.get(company_number)
        if cached_vs:
            self.vector_store = cached_vs
        else:
            # Not in cache, try to load from disk
            company_path = self.get_company_vector_store_path(company_number)
            if os.path.exists(company_path):
                try:
                    vector_store = FAISS.load_local(
                        company_path, 
                        self.embeddings,
                        allow_dangerous_deserialization=True
                    )

                    # Add to cache
                    self.company_vector_stores.put(company_number, vector_store)
                    self.vector_store = vector_store
                except Exception as e:
                    # If loading fails, process the company's PDFs
                    print(f"Error loading vector store for company {company_number}: {e}")
                    self._process_company_pdfs(company_number)
                    self.vector_store = self.company_vector_stores.get(company_number)
                    if not self.vector_store:
                        return f"Failed to process PDFs for company {company_number}."
            else:
                # No vector store exists, process the company's PDFs
                print(f"No vector store found for company {company_number}. Processing PDFs...")
                success = self._process_company_pdfs(company_number)
                if success:
                    self.vector_store = self.company_vector_stores.get(company_number)
                else:
                    return f"No PDFs found or processing failed for company {company_number}. Please upload PDFs first."

        # Now we should have a vector store for this company
        if not self.vector_store:
            return f"No data available for company {company_number}."

        # Set up and run the QA chain
        qa_chain = self.setup_qa_chain()
        answer = qa_chain.invoke(question)

        return answer


# Function to process PDFs and create vector store
def process_pdfs(company_number):
    """
    Process PDFs for a specific company and create a vector store.
    Company number is required - this function will not process all PDFs.
    """
    if not company_number:
        print("Company number is required to process PDFs.")
        return None

    processor = PDFProcessor()
    success = processor.load_and_process_pdfs(company_number)
    return processor if success else None


# Function to answer questions
def answer_question(question, company_number):
    """
    Answer a question about a specific company's PDFs.
    Company number is required.
    """
    if not question or not company_number:
        return "Both question and company number are required."

    processor = PDFProcessor()
    return processor.answer_question(question, company_number)
