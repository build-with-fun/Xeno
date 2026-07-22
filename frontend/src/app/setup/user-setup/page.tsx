'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function UserSetupPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({
    userName: '',
    email: '',
    occupation: '',
    interests: '',
    importantData: '',
    documents: [] as File[],
  });

  const handleNext = async () => {
    if (step === 2) {
      setIsLoading(true);
      // Save user data to backend
      try {
        const formDataToSend = new FormData();
        formDataToSend.append('user_name', formData.userName);
        formDataToSend.append('email', formData.email);
        formDataToSend.append('occupation', formData.occupation);
        formDataToSend.append('interests', formData.interests);
        formDataToSend.append('important_data', formData.importantData);
        
        formData.documents.forEach((doc) => {
          formDataToSend.append('documents', doc);
        });

        await fetch('http://localhost:8000/api/setup/user', {
          method: 'POST',
          body: formDataToSend,
        });
      } catch (error) {
        console.error('Error saving user data:', error);
      } finally {
        setIsLoading(false);
        setStep(step + 1);
      }
    } else {
      setStep(step + 1);
    }
  };

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1);
    } else {
      router.push('/setup/get-started');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFormData({
        ...formData,
        documents: [...formData.documents, ...Array.from(e.target.files)],
      });
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-3xl w-full">
        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex justify-between text-sm text-gray-400 mb-2">
            <span>User Info</span>
            <span>Documents</span>
            <span>Complete</span>
          </div>
          <div className="progress-bar">
            <div 
              className="progress-bar-fill" 
              style={{ width: `${(step / 3) * 100}%` }}
            ></div>
          </div>
        </div>

        <div className="glass-card p-10 card-hover">
          <h1 className="text-4xl font-bold mb-2 neon-text-cyan">User Setup</h1>
          <p className="text-gray-400 mb-8">Let's get to know you better</p>

          {step === 1 && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  Your Name *
                </label>
                <input
                  type="text"
                  value={formData.userName}
                  onChange={(e) => setFormData({ ...formData, userName: e.target.value })}
                  className="input-neon w-full"
                  placeholder="John Doe"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  Email Address
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="input-neon w-full"
                  placeholder="john@example.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  Occupation
                </label>
                <input
                  type="text"
                  value={formData.occupation}
                  onChange={(e) => setFormData({ ...formData, occupation: e.target.value })}
                  className="input-neon w-full"
                  placeholder="Software Developer"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  Interests & Hobbies
                </label>
                <textarea
                  value={formData.interests}
                  onChange={(e) => setFormData({ ...formData, interests: e.target.value })}
                  className="input-neon w-full"
                  rows={3}
                  placeholder="AI, programming, music, reading..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  Important Data (Optional)
                </label>
                <textarea
                  value={formData.importantData}
                  onChange={(e) => setFormData({ ...formData, importantData: e.target.value })}
                  className="input-neon w-full"
                  rows={4}
                  placeholder="Any important information you want Xeno to remember..."
                />
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  Upload Documents
                </label>
                <div className="border-2 border-dashed border-gray-600 rounded-xl p-8 text-center hover:border-neon-cyan transition-colors">
                  <input
                    type="file"
                    multiple
                    onChange={handleFileChange}
                    className="hidden"
                    id="file-upload"
                  />
                  <label htmlFor="file-upload" className="cursor-pointer">
                    <div className="text-5xl mb-4">📄</div>
                    <p className="text-gray-300 mb-2">
                      Drag & drop files here or click to browse
                    </p>
                    <p className="text-sm text-gray-500">
                      PDF, DOC, DOCX, TXT, MD (Max 50MB each)
                    </p>
                  </label>
                </div>

                {formData.documents.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <p className="text-sm text-gray-400">
                      {formData.documents.length} file(s) selected:
                    </p>
                    {formData.documents.map((doc, index) => (
                      <div key={index} className="glass-card p-3 flex items-center justify-between">
                        <span className="text-sm text-gray-300">{doc.name}</span>
                        <button
                          onClick={() => {
                            setFormData({
                              ...formData,
                              documents: formData.documents.filter((_, i) => i !== index),
                            });
                          }}
                          className="text-red-400 hover:text-red-300 text-sm"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="glass-card p-4 bg-opacity-30">
                <h3 className="font-semibold mb-2 neon-text-purple">💡 Pro Tip</h3>
                <p className="text-sm text-gray-400">
                  Upload important documents like resumes, project specs, or reference materials.
                  Xeno will analyze and remember them to help you better.
                </p>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="text-center py-8">
              <div className="text-6xl mb-6">✅</div>
              <h2 className="text-3xl font-bold mb-4 neon-text-cyan">User Profile Complete!</h2>
              <p className="text-gray-300 mb-8 max-w-md mx-auto">
                Your profile has been saved successfully. Xeno now knows about you and is ready to assist you better.
              </p>
            </div>
          )}

          {/* Navigation Buttons */}
          <div className="flex justify-between mt-10">
            <button
              onClick={handleBack}
              className="px-6 py-3 rounded-lg border border-gray-600 hover:border-gray-400 transition-colors"
            >
              {step === 1 ? 'Back to Start' : 'Back'}
            </button>

            {step < 3 && (
              <button
                onClick={handleNext}
                disabled={!formData.userName || isLoading}
                className="btn-neon px-8 py-3"
              >
                {isLoading ? (
                  <span className="flex items-center">
                    <div className="spinner w-5 h-5 mr-2"></div>
                    Saving...
                  </span>
                ) : (
                  'Next'
                )}
              </button>
            )}

            {step === 3 && (
              <button
                onClick={() => router.push('/setup/profiles-setup')}
                className="btn-neon px-8 py-3"
              >
                Continue to Profiles Setup
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
