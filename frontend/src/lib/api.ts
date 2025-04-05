import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001';

// Create axios instance
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests if available
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// Add response interceptor to handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle 401 Unauthorized errors by redirecting to login
    if (error.response && error.response.status === 401) {
      console.log('Unauthorized access detected, redirecting to login page');
      
      // Clear authentication data
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      
      // Redirect to login page
      if (typeof window !== 'undefined') {
        window.location.href = '/auth/login';
      }
    }
    
    return Promise.reject(error);
  }
);

export const AuthService = {
  async login(username: string, password: string) {
    const response = await api.post('/api/auth/login', { username, password });
    if (response.data.access_token) {
      localStorage.setItem('token', response.data.access_token);
    }
    return response;
  },
  
  async register(username: string, password: string) {
    const response = await api.post('/api/auth/register', { username, password });
    if (response.data.access_token) {
      localStorage.setItem('token', response.data.access_token);
    }
    return response;
  },
  
  logout() {
    localStorage.removeItem('token');
  },
  
  getToken() {
    return localStorage.getItem('token');
  },
  
  isAuthenticated() {
    return !!localStorage.getItem('token');
  }
};

export const PDFService = {
  async scrapePDFs(companyNumber: string) {
    return api.post('/scrape_pdfs', { company_number: companyNumber });
  },
  
  async processPDFs(companyNumber: string) {
    return api.post('/process_pdfs', { company_number: companyNumber });
  },
  
  async askQuestion(companyNumber: string, question: string) {
    return api.post('/ask', { 
      company_number: companyNumber,
      question: question 
    });
  }
};

export async function getCompanies() {
  try {
    const response = await fetch(`${API_URL}/companies`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${AuthService.getToken()}`
      },
    });

    if (!response.ok) {
      // Handle 401 Unauthorized errors by redirecting to login
      if (response.status === 401) {
        console.log('Unauthorized access detected, redirecting to login page');
        
        // Clear authentication data
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        
        // Redirect to login page
        if (typeof window !== 'undefined') {
          window.location.href = '/auth/login';
        }
      }
      
      throw new Error('Failed to fetch companies');
    }

    const data = await response.json();
    return data.companies;
  } catch (error) {
    console.error('Error fetching companies:', error);
    throw error;
  }
}

export default api; 