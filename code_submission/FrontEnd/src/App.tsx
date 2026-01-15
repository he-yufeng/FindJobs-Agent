import { useState } from 'react';
import Navigation from './components/Navigation';
import ResumePage from './components/ResumePage';
import JobsPage from './components/JobsPage';
import InterviewPage from './components/InterviewPage';

type Page = 'resume' | 'jobs' | 'interview';

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('resume');

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation currentPage={currentPage} onNavigate={setCurrentPage} />

      {currentPage === 'resume' && <ResumePage />}
      {currentPage === 'jobs' && <JobsPage />}
      {currentPage === 'interview' && <InterviewPage />}
    </div>
  );
}

export default App;
