import React, { useState, useEffect } from 'react';

// Main App component
const App = () => {
  const [awsAccountId, setAwsAccountId] = useState('443044514797'); // Pre-fill with user's account ID
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveredResources, setDiscoveredResources] = useState(null);
  const [error, setError] = useState(null);

  // Demo data to be used if the backend fetch fails
  const demoAwsResources = {
    'us-east-1': {
      EC2: [
        { id: 'i-0a1b2c3d4e5f6a7b8', name: 'Web-Server-Prod', type: 't2.micro', state: 'running' },
        { id: 'i-0f9e8d7c6b5a4b3c2', name: 'Dev-Instance', type: 't3.small', state: 'stopped' },
      ],
      S3: [
        { name: 'my-production-bucket', region: 'us-east-1', type: 'Public', objects: 1200 },
        { name: 'logs-archive-2024', region: 'us-east-1', type: 'Private', objects: 50000 },
      ],
      Lambda: [
        { name: 'process-order-function', runtime: 'nodejs18.x', memory: 128 },
        { name: 'user-auth-api', runtime: 'python3.9', memory: 256 },
      ],
      RDS: [
        { id: 'database-1', engine: 'MySQL', instanceClass: 'db.t3.medium', status: 'available' },
      ],
    },
    'us-west-2': {
      EC2: [
        { id: 'i-0c1d2e3f4a5b6c7d8', name: 'Backend-Service', type: 'm5.large', state: 'running' },
      ],
      S3: [
        { name: 'media-content-cdn', region: 'us-west-2', type: 'Public', objects: 5000 },
      ],
      VPC: [
        { id: 'vpc-0123456789abcdef0', name: 'Production-VPC', cidr: '10.0.0.0/16' },
      ],
    },
    'eu-west-1': {
      EC2: [
        { id: 'i-0e1f2a3b4c5d6e7f8', name: 'EU-App-Server', type: 't2.medium', state: 'running' },
      ],
      S3: [
        { name: 'eu-data-backup', region: 'eu-west-1', type: 'Private', objects: 10000 },
      ],
    },
  };

  // Function to initiate resource discovery by calling the backend
  const handleDiscoverResources = async () => {
    if (!awsAccountId) {
      setError('Please enter an AWS Account ID.');
      return;
    }

    setIsDiscovering(true);
    setDiscoveredResources(null); // Clear previous results
    setError(null); // Clear previous errors

    try {
      const backendUrl = `http://127.0.0.1:5000/discover-aws?accountId=${awsAccountId}`;
      console.log(`Attempting to fetch from: ${backendUrl}`);

      const response = await fetch(backendUrl);

      if (!response.ok) {
        let errorMessage = `HTTP error! Status: ${response.status} ${response.statusText || ''}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.error || errorMessage;
        } catch (jsonError) {
          console.warn("Backend response was not JSON:", await response.text());
        }
        // If backend returns an error or non-OK status, fall back to demo data
        console.warn(`Backend returned an error: ${errorMessage}. Displaying demonstration data.`);
        setError(`Could not retrieve live data: ${errorMessage}. Displaying demonstration data. Please ensure the backend is running and configured correctly.`);
        setDiscoveredResources(demoAwsResources);
        return; // Exit after setting demo data
      }

      const data = await response.json();
      setDiscoveredResources(data);

    } catch (err) {
      console.error("Discovery error (network/other issue):", err);
      // If 'Failed to fetch' (network error, CORS, backend not running), use demo data
      setError(`Failed to connect to the backend: ${err.message}. Displaying demonstration data. Please ensure the Python Flask backend is running on http://127.0.0.1:5000 and is accessible.`);
      setDiscoveredResources(demoAwsResources);
    } finally {
      setIsDiscovering(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-100 to-purple-200 p-8 font-sans flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-2xl p-8 w-full max-w-4xl border border-gray-200">
        <h1 className="text-4xl font-extrabold text-center text-gray-800 mb-6">
          <span className="text-blue-600">AWS</span> Resource Discovery
        </h1>
        <p className="text-center text-gray-600 mb-8 max-w-2xl mx-auto">
          Enter an AWS Account ID to initiate resource discovery for your iCoE tool.
          <br />
          <span className="font-semibold text-red-500">Note: This frontend connects to a Python backend for live data. If the backend is unreachable, demonstration data will be shown.</span>
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
          <input
            type="text"
            placeholder="Enter AWS Account ID (e.g., 443044514797)"
            value={awsAccountId}
            onChange={(e) => setAwsAccountId(e.target.value)}
            className="flex-grow p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition duration-200 ease-in-out text-gray-700 placeholder-gray-400 shadow-sm"
            aria-label="AWS Account ID"
          />
          <button
            onClick={handleDiscoverResources}
            disabled={isDiscovering}
            className={`px-6 py-3 rounded-lg text-white font-semibold transition duration-300 ease-in-out shadow-md
              ${isDiscovering ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 hover:shadow-lg'}`}
          >
            {isDiscovering ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Discovering...
              </span>
            ) : (
              'Discover Resources'
            )}
          </button>
        </div>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg relative mb-6" role="alert">
            <strong className="font-bold">Error!</strong>
            <span className="block sm:inline ml-2">{error}</span>
          </div>
        )}

        {discoveredResources && (
          <div className="bg-gray-50 p-6 rounded-lg shadow-inner border border-gray-200">
            <h2 className="text-2xl font-bold text-gray-800 mb-4 text-center">Discovered Resources for Account ID: {awsAccountId}</h2>
            {Object.entries(discoveredResources).map(([region, services]) => (
              <div key={region} className="mb-8 p-4 bg-white rounded-lg shadow-md border border-gray-100">
                <h3 className="text-xl font-semibold text-blue-700 mb-3 flex items-center">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 mr-2 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  Region: {region}
                </h3>
                {Object.entries(services).map(([serviceName, resources]) => (
                  <div key={serviceName} className="mb-6 ml-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
                    <h4 className="text-lg font-medium text-gray-700 mb-2 flex items-center">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
                      </svg>
                      Service: {serviceName} ({resources.length} resources)
                    </h4>
                    <ul className="list-disc pl-5 text-gray-600">
                      {resources.map((resource, index) => (
                        <li key={index} className="mb-1 text-sm">
                          {Object.entries(resource).map(([key, value]) => (
                            <span key={key} className="mr-3">
                              <span className="font-semibold capitalize">{key}:</span> {value}
                            </span>
                          ))}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default App;
