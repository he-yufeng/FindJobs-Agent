import { useEffect, useState } from 'react';
import { FileText, Briefcase, KanbanSquare, MessageSquare } from 'lucide-react';
import { getHealth } from '../lib/mockApi';

interface NavigationProps {
  currentPage: 'resume' | 'jobs' | 'interview' | 'applications';
  onNavigate: (page: 'resume' | 'jobs' | 'interview' | 'applications') => void;
}

export default function Navigation({ currentPage, onNavigate }: NavigationProps) {
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    getHealth()
      .then(data => setDemo(data.demo === true))
      .catch(() => setDemo(false));
  }, []);

  const navItems = [
    { id: 'resume' as const, label: '简历分析', icon: FileText },
    { id: 'jobs' as const, label: '岗位匹配', icon: Briefcase },
    { id: 'interview' as const, label: '模拟面试', icon: MessageSquare },
    { id: 'applications' as const, label: '投递看板', icon: KanbanSquare },
  ];

  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center">
                <FileText className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-semibold text-gray-900">FindBestCareers</span>
              {demo && (
                <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-700">
                  Demo
                </span>
              )}
            </div>
          </div>

          <div className="flex space-x-1">
            {navItems.map(item => {
              const Icon = item.icon;
              const isActive = currentPage === item.id;

              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className={`
                    flex items-center space-x-2 px-4 py-2 rounded-lg transition-all
                    ${isActive
                      ? 'bg-blue-50 text-blue-600 font-medium'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    }
                  `}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
