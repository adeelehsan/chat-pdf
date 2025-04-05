# PDF Question Answering System

A full-stack application that allows you to scrape, process, and query PDF documents using AI. The system features a Next.js frontend and a Flask backend with OpenAI integration.

## Features

- User authentication with username and password
- Scrape PDFs from the web using company registration numbers
- Process and store PDFs in a vector database for semantic search (company-specific)
- Interactive Q&A interface to query the content of processed PDFs
- Dropdown selection of previously indexed companies
- AI-generated answers based on the company's PDF content
- Robust PDF processing with multiple fallback methods and OCR capabilities
- Automatic redirection to login page when authentication expires

## System Architecture

The application consists of two main components:

1. **Backend**: Flask API with LangChain, OpenAI, and FAISS
2. **Frontend**: Next.js application with React and Tailwind CSS

## Project Structure

```
chat-pdf/
├── backend/                  # Flask backend
│   ├── downloaded_pdfs/      # PDF storage (ignored by git)
│   ├── vector_store/         # Vector embeddings (ignored by git)
│   ├── app.py                # Main Flask application
│   ├── auth.py               # Authentication logic
│   ├── process_qa.py         # PDF processing and Q&A logic
│   ├── requirements.txt      # Python dependencies
│   ├── scraper.py            # PDF scraping functionality
│   └── test_pdf_extraction.py # Testing script for PDF extraction
│
├── frontend/                 # Next.js frontend (regular directory, not a git submodule)
│   ├── components/           # React components
│   ├── pages/                # Next.js pages
│   ├── public/               # Static assets
│   ├── styles/               # CSS styles
│   ├── package.json          # JavaScript dependencies
│   └── next.config.js        # Next.js configuration
│
├── .gitignore                # Git ignore rules for both backend and frontend
└── README.md                 # This file
```

## Backend Setup

For processing scanned PDFs where text is embedded in images (like scanned financial documents), you'll need:

1. **Poppler** - Required for converting PDF pages to images
   - **MacOS**: `brew install poppler`

2. **Tesseract OCR** - Required for extracting text from images
   - **MacOS**: `brew install tesseract`


1. Set up a Python virtual environment (recommended):
   ```bash
   cd chat-pdf/backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   - Create a `.env` file in the `backend` directory
   - Add your OpenAI API key:
     ```
     OPENAI_API_KEY=your_openai_api_key_here
     ```

4. Start the backend server:
   ```bash
   python app.py
   ```
   
   The server will run on `http://localhost:5001`

## Frontend Setup

1. Install Node.js dependencies:
   ```bash
   cd chat-pdf/frontend
   npm install
   ```

2. Set up environment variables:
   - Create a `.env.local` file in the frontend directory
   - Add the API URL:
     ```
     NEXT_PUBLIC_API_URL=http://localhost:5001
     ```

3. Start the development server:
   ```bash
   npm run dev
   ```
   
   The frontend will run on `http://localhost:3000`

## API Endpoints

### Authentication
- **Login**: `POST /api/auth/login`
  ```json
  {
    "username": "yourUsername",
    "password": "yourPassword"
  }
  ```

- **Register**: `POST /api/auth/register`
  ```json
  {
    "username": "newUsername",
    "password": "newPassword"
  }
  ```

### PDF Management
- **Scrape PDFs**: `POST /scrape_pdfs`
  ```json
  {
    "company_number": "12345678"
  }
  ```

- **Process PDFs**: `POST /process_pdfs`
  ```json
  {
    "company_number": "12345678"
  }
  ```

- **Ask Questions**: `POST /ask`
  ```json
  {
    "question": "What is the revenue of company X in 2022?",
    "company_number": "12345678"
  }
  ```

- **List Indexed Companies**: `GET /companies`
  - Returns a list of companies that have been indexed and are available for Q&A

## How It Works

### PDF Processing Flow

1. **Scraping**: PDFs are downloaded to the `backend/downloaded_pdfs/` directory
   - Each company's PDFs are stored in a subfolder named with the company number

2. **Processing**: Documents are loaded, chunked, and vectorized for efficient searching
   - Multiple PDF loading methods are attempted for optimal extraction:
     - PyPDFLoader (fast)
     - PDFPlumberLoader (robust)
     - Direct PyPDF approach with error recovery
     - OCR using Tesseract (for scanned documents)

3. **Indexing**: Vectors are stored in a FAISS database for fast similarity search
   - Each company has its own isolated vector store at `backend/vector_store/{company_number}/`

4. **Memory Management**:
   - An LRU (Least Recently Used) cache keeps only recent vector stores in memory
   - By default, only the 5 most recently used company vector stores are kept in memory

### Question Answering Process

1. User selects a company from the dropdown or processes a new company
2. When a question is asked about a specific company:
   - The system retrieves the company's vector store (from memory or disk)
   - If the vector store doesn't exist, it processes the company's PDFs first
   - The question is vectorized and used to find relevant chunks in the vector store
   - The relevant chunks and question are sent to the LLM to generate an answer
   - The answer is returned to the user interface

## Frontend Structure

- **Authentication**: Login and registration pages with token-based auth
- **Dashboard**: Company number input for processing new PDFs
- **Q&A Interface**: Question form and answer display with company selector

## Security Features

- JWT-based authentication
- Automatic redirection to login when sessions expire (401 responses)
- Error handling for API failures
- Input validation

## Troubleshooting

- Make sure your OpenAI API key is valid and has sufficient credits
- Ensure both backend and frontend servers are running
- Check for CORS issues if running on different domains
- For PDF processing issues:
  - Confirm the PDFs are not password protected
  - For scanned documents, ensure OCR is properly installed
  - Check server logs for detailed processing information

## Dependencies

### Backend
- Flask: Web framework
- LangChain: Framework for working with LLMs
- OpenAI: For embeddings and LLM capabilities
- FAISS: Vector database for efficient similarity search
- PyPDF and PDF Plumber: For processing PDF documents
- Tesseract & pdf2image: For OCR capabilities

### Frontend
- Next.js: React framework
- Tailwind CSS: Utility-first CSS framework
- Axios: HTTP client
- React Hook Form: Form validation 