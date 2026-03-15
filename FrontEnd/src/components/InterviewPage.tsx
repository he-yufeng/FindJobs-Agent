import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, ArrowLeft, Briefcase, MapPin, Download } from 'lucide-react';
import { InterviewMessage, JobPosition } from '../types';
import { startInterview, simulateInterviewChat } from '../lib/mockApi';

interface InterviewPageProps {
  job: JobPosition | null;
  onBack: () => void;
}

// Parse AI message to detect score cards and structure
function renderFormattedMessage(content: string, role: string) {
  if (role === 'user') {
    return <p className="text-sm leading-relaxed whitespace-pre-wrap">{content}</p>;
  }

  // Split by lines and render with formatting
  const lines = content.split('\n');
  const elements: JSX.Element[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Score line: [Score: X/5]
    const scoreMatch = line.match(/\[(?:Score|Last question score):\s*(\d)\/5\]/);
    if (scoreMatch) {
      const score = parseInt(scoreMatch[1]);
      const colors = ['bg-red-500', 'bg-red-400', 'bg-orange-400', 'bg-yellow-400', 'bg-blue-500', 'bg-green-500'];
      elements.push(
        <div key={i} className="flex items-center gap-2 my-2">
          <div className={`${colors[score]} text-white px-3 py-1.5 rounded-lg font-bold text-sm flex items-center gap-1`}>
            <span className="text-lg">{score}</span>/5
          </div>
          <div className="flex gap-0.5">
            {[1,2,3,4,5].map(n => (
              <div key={n} className={`w-6 h-2 rounded-full ${n <= score ? colors[score] : 'bg-gray-200'}`} />
            ))}
          </div>
        </div>
      );
      i++;
      continue;
    }

    // Strengths line
    if (line.startsWith('Strengths:') || line.startsWith('Strength:')) {
      elements.push(
        <div key={i} className="bg-green-50 border-l-3 border-green-400 pl-3 py-1.5 my-1.5 rounded-r-lg">
          <span className="text-green-700 text-sm font-medium">✓ </span>
          <span className="text-green-800 text-sm">{line.replace(/^Strengths?:\s*/, '')}</span>
        </div>
      );
      i++;
      continue;
    }

    // Improvements line
    if (line.startsWith('Improvements:') || line.startsWith('Improvement:')) {
      elements.push(
        <div key={i} className="bg-amber-50 border-l-3 border-amber-400 pl-3 py-1.5 my-1.5 rounded-r-lg">
          <span className="text-amber-700 text-sm font-medium">△ </span>
          <span className="text-amber-800 text-sm">{line.replace(/^Improvements?:\s*/, '')}</span>
        </div>
      );
      i++;
      continue;
    }

    // Question line
    const qMatch = line.match(/^Question\s+(\d+):/);
    if (qMatch) {
      elements.push(
        <div key={i} className="bg-blue-50 border border-blue-200 rounded-lg p-3 my-2">
          <span className="text-blue-600 text-xs font-bold uppercase tracking-wider">问题 {qMatch[1]}</span>
          <p className="text-blue-900 text-sm mt-1 font-medium">{line.replace(/^Question\s+\d+:\s*/, '')}</p>
        </div>
      );
      i++;
      continue;
    }

    // "Final Feedback Report" header
    if (line.includes('Final Feedback Report') || line.includes('feedback report')) {
      elements.push(
        <div key={i} className="bg-gradient-to-r from-purple-600 to-blue-600 text-white px-4 py-2.5 rounded-lg my-3 font-semibold text-sm">
          📋 {line}
        </div>
      );
      i++;
      continue;
    }

    // Regular line
    if (line.trim()) {
      elements.push(
        <p key={i} className="text-sm leading-relaxed text-gray-800">{line}</p>
      );
    } else {
      elements.push(<div key={i} className="h-2" />);
    }
    i++;
  }

  return <div className="space-y-0.5">{elements}</div>;
}

export default function InterviewPage({ job, onBack }: InterviewPageProps) {
  const [messages, setMessages] = useState<InterviewMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionStarted, setSessionStarted] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questionCount, setQuestionCount] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  if (!job) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 bg-gray-200 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Briefcase className="w-8 h-8 text-gray-400" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">请先选择一个岗位</h2>
          <p className="text-gray-600 mb-6">在岗位匹配页面中，点击"模拟面试"按钮即可开始。</p>
          <button onClick={onBack} className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium">
            前往岗位匹配
          </button>
        </div>
      </div>
    );
  }

  const handleStartInterview = async () => {
    setSessionStarted(true);
    setIsLoading(true);
    setQuestionCount(0);
    try {
      const resumeId = localStorage.getItem('current_resume_id') || undefined;
      const result = await startInterview(resumeId, job.id);
      setSessionId(result.sessionId);
      setMessages([{
        id: crypto.randomUUID(),
        session_id: result.sessionId,
        role: 'assistant',
        content: result.message,
        created_at: new Date().toISOString()
      }]);
    } catch (error) {
      alert('开始面试失败: ' + (error instanceof Error ? error.message : '未知错误'));
      setSessionStarted(false);
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading || !sessionId) return;
    const userMessage: InterviewMessage = {
      id: crypto.randomUUID(), session_id: sessionId, role: 'user',
      content: inputValue, created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);
    const currentInput = inputValue;
    setInputValue('');
    setIsLoading(true);
    try {
      const response = await simulateInterviewChat(sessionId, currentInput);
      // Count questions
      const qMatch = response.match(/Question\s+(\d+):/g);
      if (qMatch) setQuestionCount(prev => Math.max(prev, qMatch.length));
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(), session_id: sessionId, role: 'assistant',
        content: response, created_at: new Date().toISOString()
      }]);
    } catch (error) {
      alert('发送失败: ' + (error instanceof Error ? error.message : '未知错误'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const exportTranscript = () => {
    const text = messages.map(m => `[${m.role === 'user' ? '我' : 'AI面试官'}]\n${m.content}`).join('\n\n---\n\n');
    const header = `FindBestCareers 面试记录\n岗位：${job.title} - ${job.company}\n日期：${new Date().toLocaleDateString()}\n\n${'='.repeat(50)}\n\n`;
    const blob = new Blob([header + text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `面试记录_${job.title}_${new Date().toISOString().split('T')[0]}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Back + Job info header */}
        <div className="mb-6">
          <button onClick={onBack} className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 transition-colors mb-4">
            <ArrowLeft className="w-4 h-4" /><span>返回岗位列表</span>
          </button>
          <div className="bg-white rounded-xl shadow-sm p-5 border border-blue-100">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center space-x-2 mb-1">
                  <Briefcase className="w-5 h-5 text-blue-600" />
                  <span className="text-sm font-medium text-blue-600">模拟面试目标岗位</span>
                </div>
                <h2 className="text-xl font-bold text-gray-900">{job.title}</h2>
                <div className="flex items-center space-x-3 mt-1 text-sm text-gray-600">
                  <span className="font-medium">{job.company}</span>
                  {job.location && <span className="flex items-center space-x-1"><MapPin className="w-3.5 h-3.5" /><span>{job.location}</span></span>}
                </div>
              </div>
              {/* Progress indicator */}
              {sessionStarted && (
                <div className="text-right">
                  <span className="text-xs text-gray-400">面试进度</span>
                  <div className="flex gap-1 mt-1">
                    {[1,2,3,4,5].map(n => (
                      <div key={n} className={`w-5 h-1.5 rounded-full ${n <= questionCount ? 'bg-blue-500' : 'bg-gray-200'}`} />
                    ))}
                  </div>
                </div>
              )}
            </div>
            {job.required_skills && job.required_skills.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {job.required_skills.slice(0, 8).map((skill, i) => (
                  <span key={i} className="px-2.5 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-full">{skill}</span>
                ))}
                {job.required_skills.length > 8 && <span className="px-2.5 py-1 bg-gray-100 text-gray-500 text-xs rounded-full">+{job.required_skills.length - 8}</span>}
              </div>
            )}
          </div>
        </div>

        {!sessionStarted ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-22rem)]">
            <div className="text-center max-w-2xl">
              <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <Sparkles className="w-10 h-10 text-white" />
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-3">AI 模拟面试</h1>
              <p className="text-lg text-gray-600 mb-8 leading-relaxed">
                针对 <span className="font-semibold text-blue-600">{job.title}</span> 岗位，
                AI 面试官将根据岗位要求为您进行针对性的面试模拟训练。
              </p>
              <div className="bg-white rounded-xl shadow-sm p-8 mb-8">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">面试流程</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
                  {[
                    ['1', '自我介绍', '结合目标岗位介绍您的背景'],
                    ['2', '岗位技术问答', '针对岗位技能要求的 5 道专业问题'],
                    ['3', '面试反馈报告', '获得针对该岗位的改进建议'],
                  ].map(([num, title, desc]) => (
                    <div key={num} className="flex flex-col">
                      <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-semibold mb-3">{num}</div>
                      <h3 className="font-medium text-gray-900 mb-2">{title}</h3>
                      <p className="text-sm text-gray-600">{desc}</p>
                    </div>
                  ))}
                </div>
              </div>
              <button onClick={handleStartInterview} className="px-8 py-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl hover:from-purple-700 hover:to-blue-700 transition-all font-semibold text-lg shadow-lg hover:shadow-xl">
                开始模拟面试
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col h-[calc(100vh-22rem)]">
            <div className="bg-white rounded-t-xl shadow-sm p-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-blue-600 rounded-full flex items-center justify-center">
                    <Bot className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h2 className="font-semibold text-gray-900">AI 面试官</h2>
                    <p className="text-sm text-gray-500">面试中 · {job.title}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={exportTranscript} className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-1">
                    <Download className="w-3.5 h-3.5" />导出记录
                  </button>
                  <button
                    onClick={() => { setSessionStarted(false); setMessages([]); setSessionId(null); setQuestionCount(0); }}
                    className="px-4 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    结束面试
                  </button>
                </div>
              </div>
            </div>

            <div className="flex-1 bg-gray-50 overflow-y-auto p-6 space-y-4">
              {messages.map(message => (
                <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`flex items-start space-x-3 max-w-[85%] ${message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                      message.role === 'user' ? 'bg-gray-200' : 'bg-gradient-to-br from-purple-500 to-blue-600'
                    }`}>
                      {message.role === 'user' ? <User className="w-5 h-5 text-gray-700" /> : <Bot className="w-5 h-5 text-white" />}
                    </div>
                    <div className={`px-4 py-3 rounded-2xl ${
                      message.role === 'user' ? 'bg-blue-600 text-white' : 'bg-white text-gray-900 shadow-sm'
                    }`}>
                      {renderFormattedMessage(message.content, message.role)}
                    </div>
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-start">
                  <div className="flex items-start space-x-3">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-gradient-to-br from-purple-500 to-blue-600">
                      <Bot className="w-5 h-5 text-white" />
                    </div>
                    <div className="bg-white px-4 py-3 rounded-2xl shadow-sm">
                      <div className="flex space-x-2">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="bg-white rounded-b-xl shadow-sm p-4 border-t border-gray-200">
              <div className="flex items-end space-x-3">
                <textarea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="输入您的回答..."
                  disabled={isLoading}
                  rows={1}
                  className="flex-1 resize-none border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50"
                  style={{ minHeight: '48px', maxHeight: '120px' }}
                />
                <button onClick={sendMessage} disabled={!inputValue.trim() || isLoading}
                  className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0">
                  <Send className="w-5 h-5" />
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-2">按 Enter 发送，Shift + Enter 换行</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
