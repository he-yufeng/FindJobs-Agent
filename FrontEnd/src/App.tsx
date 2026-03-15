import { useState } from 'react';
import Navigation from './components/Navigation';
import ResumePage from './components/ResumePage';
import JobsPage from './components/JobsPage';
import InterviewPage from './components/InterviewPage';
import { JobPosition, Resume, ResumeSkill } from './types';

type Page = 'resume' | 'jobs' | 'interview';

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('resume');
  const [selectedJob, setSelectedJob] = useState<JobPosition | null>(null);
  const [resume, setResume] = useState<Resume | null>(null);
  const [skills, setSkills] = useState<ResumeSkill[]>([]);

  const handleStartJobInterview = (job: JobPosition) => {
    setSelectedJob(job);
    setCurrentPage('interview');
  };

  const handleBackToJobs = () => {
    setSelectedJob(null);
    setCurrentPage('jobs');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation currentPage={currentPage} onNavigate={(page) => {
        if (page !== 'interview') {
          setSelectedJob(null);
        }
        setCurrentPage(page);
      }} />

      {currentPage === 'resume' && (
        <ResumePage
          resume={resume}
          skills={skills}
          onResumeChange={setResume}
          onSkillsChange={setSkills}
        />
      )}
      {currentPage === 'jobs' && <JobsPage onStartInterview={handleStartJobInterview} />}
      {currentPage === 'interview' && <InterviewPage job={selectedJob} onBack={handleBackToJobs} />}
    </div>
  );
}

export default App;
