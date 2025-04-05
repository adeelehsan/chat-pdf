'use client';

import { useState, useEffect } from 'react';
import { useForm, SubmitHandler } from 'react-hook-form';
import { PDFService, getCompanies } from '@/lib/api';
import Header from '@/components/Header';
import ProtectedRoute from '@/components/ProtectedRoute';
import LoadingSpinner from '@/components/LoadingSpinner';
import { useRouter } from 'next/navigation';

type CompanyFormInputs = {
  companyNumber: string;
};

enum ProcessingStatus {
  IDLE = 'idle',
  SCRAPING = 'scraping',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  ERROR = 'error',
}

export default function Dashboard() {
  const [status, setStatus] = useState<ProcessingStatus>(ProcessingStatus.IDLE);
  const [error, setError] = useState('');
  const [companyNumber, setCompanyNumber] = useState('');
  const [indexedCompanies, setIndexedCompanies] = useState<string[]>([]);
  const [loadingCompanies, setLoadingCompanies] = useState(true);
  const router = useRouter();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CompanyFormInputs>();

  // Load indexed companies (we still keep this to refresh after processing)
  useEffect(() => {
    async function fetchIndexedCompanies() {
      try {
        setLoadingCompanies(true);
        const companies = await getCompanies();
        setIndexedCompanies(companies);
      } catch (err) {
        console.error('Failed to fetch indexed companies:', err);
      } finally {
        setLoadingCompanies(false);
      }
    }

    fetchIndexedCompanies();
  }, []);

  const onSubmit: SubmitHandler<CompanyFormInputs> = async (data) => {
    setError('');
    setCompanyNumber(data.companyNumber);
    
    try {
      // Step 1: Scrape PDFs
      setStatus(ProcessingStatus.SCRAPING);
      await PDFService.scrapePDFs(data.companyNumber);
      
      // Step 2: Process PDFs
      setStatus(ProcessingStatus.PROCESSING);
      await PDFService.processPDFs(data.companyNumber);
      
      // Step 3: Complete
      setStatus(ProcessingStatus.COMPLETED);
      
      // Refresh the list of indexed companies (keep this for state consistency)
      const companies = await getCompanies();
      setIndexedCompanies(companies);
      
    } catch (err: any) {
      setStatus(ProcessingStatus.ERROR);
      setError(err.response?.data?.message || 'An error occurred');
      console.error(err);
    }
  };

  const handleGoToQA = (companyNum: string = companyNumber) => {
    router.push(`/qa?companyNumber=${companyNum}`);
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-100">
        <Header />
        <main className="py-10">
          <div className="max-w-3xl mx-auto sm:px-6 lg:px-8">
            {/* Process new company section */}
            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <h1 className="text-2xl font-semibold text-gray-900 mb-6">Dashboard</h1>
                
                {status === ProcessingStatus.IDLE && (
                  <div className="bg-gray-50 p-6 rounded-lg border border-gray-200">
                    <h3 className="text-md font-medium text-gray-900 mb-4">Enter Company Number</h3>
                    <form onSubmit={handleSubmit(onSubmit)}>
                      <div className="mb-4">
                        <label htmlFor="companyNumber" className="block text-sm font-medium text-gray-700">
                          Company Number
                        </label>
                        <input
                          type="text"
                          id="companyNumber"
                          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm text-black"
                          placeholder="Enter company number"
                          {...register('companyNumber', { required: 'Company number is required' })}
                        />
                        {errors.companyNumber && (
                          <p className="mt-1 text-sm text-red-600">{errors.companyNumber.message}</p>
                        )}
                      </div>
                      <button
                        type="submit"
                        className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                      >
                        Start Processing
                      </button>
                    </form>
                  </div>
                )}

                {status === ProcessingStatus.SCRAPING && (
                  <div className="text-center py-10">
                    <LoadingSpinner />
                    <p className="mt-4 text-lg font-medium text-gray-700">Scraping PDFs for company {companyNumber}...</p>
                    <p className="mt-2 text-sm text-gray-500">This might take a few minutes.</p>
                  </div>
                )}

                {status === ProcessingStatus.PROCESSING && (
                  <div className="text-center py-10">
                    <LoadingSpinner />
                    <p className="mt-4 text-lg font-medium text-gray-700">Processing PDFs for company {companyNumber}...</p>
                    <p className="mt-2 text-sm text-gray-500">This might take a few minutes.</p>
                  </div>
                )}

                {status === ProcessingStatus.COMPLETED && (
                  <div className="text-center py-10">
                    <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
                      <svg
                        className="h-6 w-6 text-green-600"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        aria-hidden="true"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    </div>
                    <h3 className="mt-3 text-lg font-medium text-gray-900">Processing complete!</h3>
                    <p className="mt-2 text-sm text-gray-500">
                      The PDFs for company {companyNumber} have been processed successfully.
                    </p>
                    <div className="mt-6">
                      <button
                        type="button"
                        onClick={() => handleGoToQA()}
                        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                      >
                        Go to Q&A
                      </button>
                    </div>
                  </div>
                )}

                {status === ProcessingStatus.ERROR && (
                  <div className="text-center py-10">
                    <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
                      <svg
                        className="h-6 w-6 text-red-600"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        aria-hidden="true"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </div>
                    <h3 className="mt-3 text-lg font-medium text-gray-900">Processing error</h3>
                    <p className="mt-2 text-sm text-red-600">{error || 'An error occurred while processing the PDFs.'}</p>
                    <div className="mt-6">
                      <button
                        type="button"
                        onClick={() => setStatus(ProcessingStatus.IDLE)}
                        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                      >
                        Try Again
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
} 