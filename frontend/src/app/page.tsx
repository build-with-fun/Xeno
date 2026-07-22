'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const router = useRouter();
  const [isSetupComplete, setIsSetupComplete] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check if setup is complete
    const checkSetup = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/setup/status');
        const data = await response.json();
        setIsSetupComplete(data.completed);
      } catch (error) {
        console.error('Error checking setup status:', error);
        // If API is not available, assume setup is not complete
        setIsSetupComplete(false);
      } finally {
        setIsLoading(false);
      }
    };

    checkSetup();
  }, []);

  useEffect(() => {
    if (!isLoading) {
      if (isSetupComplete) {
        router.push('/main');
      } else {
        router.push('/setup/get-started');
      }
    }
  }, [isLoading, isSetupComplete, router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="spinner mx-auto mb-6"></div>
        <h1 className="text-3xl font-bold neon-text-cyan mb-2">Xeno AI</h1>
        <p className="text-gray-400">Initializing super advanced agent system...</p>
      </div>
    </div>
  );
}
