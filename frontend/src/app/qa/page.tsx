'use client';

import { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useForm, SubmitHandler } from 'react-hook-form';
import { PDFService, getCompanies } from '@/lib/api';
import Header from '@/components/Header';
import ProtectedRoute from '@/components/ProtectedRoute';
import LoadingSpinner from '@/components/LoadingSpinner';
import { useRouter } from 'next/navigation';

type QuestionFormInputs = {
  question: string;
  companyNumber: string;
};

type Message = {
  role: 'user' | 'assistant';
  content: string;
};

export default function QAPage() {
  const searchParams = useSearchParams();
  const initialCompanyNumber = searchParams.get('companyNumber');
  const [companies, setCompanies] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fetchingCompanies, setFetchingCompanies] = useState(true);
  const [error, setError] = useState('');
  const router = useRouter();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<QuestionFormInputs>({
    defaultValues: {
      companyNumber: initialCompanyNumber || '',
    }
  });

  const selectedCompanyNumber = watch('companyNumber');

  // Load the list of indexed companies
  useEffect(() => {
    async function loadCompanies() {
      try {
        setFetchingCompanies(true);
        const companyList = await getCompanies();
        setCompanies(companyList);
        
        // If no company is selected but we have companies in the list, select the first one
        if (!selectedCompanyNumber && companyList.length > 0) {
          setValue('companyNumber', initialCompanyNumber || companyList[0]);
        }
      } catch (err) {
        console.error('Failed to load companies:', err);
        setError('Failed to load the list of companies');
      } finally {
        setFetchingCompanies(false);
      }
    }

    loadCompanies();
  }, [initialCompanyNumber, setValue]);

  // Scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const onSubmit: SubmitHandler<QuestionFormInputs> = async (data) => {
    if (!data.companyNumber) {
      setError('Please select a company');
      return;
    }
    
    setError('');
    setIsLoading(true);
    
    // Add user question to messages
    const userMessage: Message = { role: 'user', content: data.question };
    setMessages((prev) => [...prev, userMessage]);
    
    try {
      // Send question to API
      const response = await PDFService.askQuestion(data.companyNumber, data.question);
      
      // Add API response to messages
      const assistantMessage: Message = { 
        role: 'assistant', 
        content: response.data.answer || 'Sorry, I couldn\'t find an answer to that question.' 
      };
      setMessages((prev) => [...prev, assistantMessage]);
      
      // Reset only the question field
      reset({ ...data, question: '' });
    } catch (err: any) {
      setError(err.response?.data?.message || 'An error occurred');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-100 flex flex-col">
        <Header />
        <main className="flex-1 py-6">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="bg-white shadow sm:rounded-lg flex flex-col h-[calc(100vh-12rem)]">
              <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
                <div className="flex flex-col md:flex-row md:items-center justify-between">
                  <h2 className="text-lg font-medium text-gray-900">Q&A Interface</h2>
                  
                  <div className="mt-2 md:mt-0 flex items-center">
                    <label htmlFor="companyNumber" className="block text-sm font-medium text-gray-700 mr-2">
                      Company:
                    </label>
                    <select
                      id="companyNumber"
                      className="block w-full pl-3 pr-10 py-2 text-black border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
                      {...register('companyNumber', { required: 'Please select a company' })}
                      disabled={fetchingCompanies}
                    >
                      {fetchingCompanies ? (
                        <option value="">Loading companies...</option>
                      ) : companies.length > 0 ? (
                        companies.map(company => (
                          <option key={company} value={company}>
                            {company}
                          </option>
                        ))
                      ) : (
                        <option value="">No companies indexed</option>
                      )}
                    </select>
                  </div>
                </div>
                <p className="mt-1 text-sm text-gray-500">
                  Ask questions about the processed PDF documents.
                </p>
              </div>
              
              {/* Messages area */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 ? (
                  <div className="text-center text-gray-500 my-8">
                    <p>Ask a question to get started</p>
                  </div>
                ) : (
                  messages.map((message, index) => (
                    <div 
                      key={index}
                      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div 
                        className={`max-w-3/4 px-4 py-2 rounded-lg ${
                          message.role === 'user' 
                            ? 'bg-blue-600 text-white' 
                            : 'bg-gray-100 text-gray-900'
                        }`}
                      >
                        <p className="whitespace-pre-wrap">{message.content}</p>
                      </div>
                    </div>
                  ))
                )}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="max-w-3/4 px-4 py-2 rounded-lg bg-gray-100">
                      <LoadingSpinner />
                    </div>
                  </div>
                )}
                {error && (
                  <div className="flex justify-center">
                    <div className="px-4 py-2 rounded-lg bg-red-100 text-red-800">
                      {error}
                    </div>
                  </div>
                )}
                {/* This div is used to scroll to bottom */}
                <div ref={messagesEndRef} />
              </div>
              
              {/* Question form */}
              <div className="border-t border-gray-200 px-4 py-4">
                <form onSubmit={handleSubmit(onSubmit)} className="flex space-x-3">
                  <div className="flex-1">
                    <label htmlFor="question" className="sr-only">Question</label>
                    <textarea
                      id="question"
                      rows={3}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm resize-none text-black"
                      placeholder="Ask a question..."
                      {...register('question', { required: 'Please enter a question' })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSubmit(onSubmit)();
                        }
                      }}
                    />
                    {errors.question && (
                      <p className="mt-1 text-sm text-red-600">{errors.question.message}</p>
                    )}
                  </div>
                  <button
                    type="submit"
                    disabled={isLoading || !selectedCompanyNumber}
                    className="inline-flex items-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-blue-300"
                  >
                    Send
                  </button>
                </form>
              </div>
            </div>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
} 