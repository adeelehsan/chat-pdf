from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import scraper
import process_qa
from auth import init_auth, authenticate_user, register_user
from flask_jwt_extended import jwt_required, get_jwt_identity

app = Flask(__name__)
CORS(app)

# Initialize authentication
init_auth(app)

# Define the base directory for downloads relative to this script's location
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "downloaded_pdfs")

# Ensure the main download folder exists when the app starts
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


@app.route('/api/auth/login', methods=['POST'])
def login():
    """
    API endpoint for user login
    Expects JSON: {"username": "user1", "password": "password123"}
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    access_token = authenticate_user(username, password)
    
    if access_token:
        return jsonify({
            "success": True,
            "message": "Login successful",
            "access_token": access_token,
            "username": username
        }), 200
    else:
        return jsonify({
            "success": False,
            "message": "Invalid username or password"
        }), 401


@app.route('/api/auth/register', methods=['POST'])
def register():
    """
    API endpoint for user registration
    Expects JSON: {"username": "newuser", "password": "password123"}
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    # Validate password strength if needed
    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must be at least 6 characters long"
        }), 400

    success, message = register_user(username, password)
    
    if success:
        access_token = authenticate_user(username, password)
        return jsonify({
            "success": True,
            "message": message,
            "access_token": access_token,
            "username": username
        }), 201
    else:
        return jsonify({
            "success": False,
            "message": message
        }), 400


@app.route('/scrape_pdfs', methods=['POST'])
@jwt_required()  # Require JWT authentication
def handle_scrape_request():
    """
    API endpoint to trigger PDF scraping for a given company number.
    Expects JSON: {"company_number": "12345678"}
    """
    # Get current user identity from JWT token
    current_user = get_jwt_identity()
    
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    company_number = data.get('company_number')

    if not company_number:
        return jsonify({"error": "Missing 'company_number' in request body"}), 400

    # Basic validation (can be enhanced)
    if not isinstance(company_number, str):
        return jsonify({"error": "Invalid 'company_number' format"}), 400

    print(f"User {current_user} requested scrape for company number: {company_number}")

    try:
        # Call the scraper function
        downloaded_files = scraper.download_company_pdfs(company_number,
                                                         DOWNLOAD_FOLDER)

        # Provide feedback based on the result
        if downloaded_files:
            return jsonify({
                "message": f"Successfully downloaded {len(downloaded_files)} accounts PDF(s) for company {company_number}.",
                "company_number": company_number,
                "download_count": len(downloaded_files),
                # Optionally return the list of filenames (relative or absolute paths)
                "files": [os.path.basename(f) for f in downloaded_files]
            }), 200
        else:
            # Check if the company folder was created but is empty (e.g., no accounts found)
            company_folder = os.path.join(DOWNLOAD_FOLDER, str(company_number))
            if os.path.exists(company_folder):
                message = f"Scraping completed for company {company_number}, but no 'accounts' PDFs were found or downloaded."
            else:
                # This case might indicate an earlier error, like company not found
                message = f"Scraping attempt finished for company {company_number}. No folder created, potentially company not found or initial access error."

            return jsonify({
                "message": message,
                "company_number": company_number,
                "download_count": 0,
                "files": []
            }), 200  # Return 200 as the process finished, even if no files found

    except ValueError as ve:  # Catch specific errors like invalid input
        print(f"Validation Error: {ve}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        # Catch any other unexpected errors during scraping
        print(f"An unexpected error occurred during scraping for {company_number}: {e}")
        # Log the full traceback for debugging on the server
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"An internal server error occurred while scraping. Check server logs."}), 500


@app.route('/process_pdfs', methods=['POST'])
@jwt_required()  # Require JWT authentication
def handle_process_pdfs():
    """
    API endpoint to process downloaded PDFs and create a vector store for Q&A.
    Requires a specific company number - will only process PDFs for that company.
    """
    # Get current user identity from JWT token
    current_user = get_jwt_identity()
    
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
            
        data = request.get_json()
        company_number = data.get('company_number')
        
        if not company_number:
            return jsonify({
                "error": "Missing 'company_number' in request body. Company number is required.",
                "success": False
            }), 400
        
        print(f"User {current_user} requested processing for company number: {company_number}")
        
        processor = process_qa.process_pdfs(company_number)
        if processor:
            return jsonify({
                "message": f"Successfully processed PDFs and created vector store for company {company_number}.",
                "company_number": company_number,
                "success": True
            }), 200
        else:
            return jsonify({
                "error": f"Failed to process PDFs for company {company_number}. Check if PDFs exist in the download folder.",
                "company_number": company_number,
                "success": False
            }), 400
    except Exception as e:
        # Catch any unexpected errors during processing
        print(f"An unexpected error occurred during PDF processing: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": f"An error occurred while processing PDFs: {str(e)}",
            "success": False
        }), 500


@app.route('/companies', methods=['GET'])
def list_companies():
    """
    Returns a list of company numbers that have been indexed in the vector store.
    """
    try:
        # Path to the vector store directory
        vector_store_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vector_store")
        
        # Get list of subdirectories in the vector store path (each is a company number)
        if os.path.exists(vector_store_path):
            company_numbers = [dir_name for dir_name in os.listdir(vector_store_path) 
                              if os.path.isdir(os.path.join(vector_store_path, dir_name))]
            
            return jsonify({
                "status": "success",
                "companies": company_numbers
            }), 200
        else:
            return jsonify({
                "status": "success",
                "companies": []
            }), 200
            
    except Exception as e:
        print(f"Error listing companies: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/ask', methods=['POST'])
@jwt_required()  # Require JWT authentication
def handle_question_api():
    """
    API endpoint to answer questions about a specific company's processed PDFs.
    Expects JSON: {"question": "What is...?", "company_number": "12345678"}
    Company number is required - will only search within that company's documents.
    """
    # Get current user identity from JWT token
    current_user = get_jwt_identity()
    
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    question = data.get('question')
    company_number = data.get('company_number')

    if not question:
        return jsonify({"error": "Missing 'question' in request body"}), 400
        
    if not company_number:
        return jsonify({"error": "Missing 'company_number' in request body. Please specify which company you want to ask about."}), 400

    print(f"User {current_user} asked question about company number: {company_number}")
    
    try:
        # Process will happen on-demand in the answer_question method
        answer = process_qa.answer_question(question, company_number)
        
        return jsonify({
            "question": question,
            "answer": answer,
            "company_number": company_number,
            "success": True
        }), 200
    except Exception as e:
        print(f"An error occurred while answering the question: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": f"An error occurred while answering the question: {str(e)}",
            "question": question,
            "company_number": company_number,
            "success": False
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
