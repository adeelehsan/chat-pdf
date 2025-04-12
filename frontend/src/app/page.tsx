'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import LoadingSpinner from '@/components/LoadingSpinner';

export default function Home() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading) {
      if (user) {
        router.push('/dashboard/');
      } else {
        router.push('/auth/login/');
      }
    }
  }, [user, isLoading, router]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
      <h1 className="text-2xl font-semibold mb-4">PDF Chat Application</h1>
      <div className="text-center">
        <LoadingSpinner />
        <p className="mt-4 text-gray-600">Redirecting...</p>
      </div>
    </div>
  );
}
