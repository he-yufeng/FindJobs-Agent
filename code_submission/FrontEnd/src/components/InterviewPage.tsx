import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles } from 'lucide-react';
import { InterviewMessage } from '../types';
import { startInterview, simulateInterviewChat } from '../lib/mockApi';

export default function InterviewPage() {
  const [messages, setMessages] = useState<InterviewMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionStarted, setSessionStarted] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleStartInterview = async () => {
    setSessionStarted(true);
    setIsLoading(true);

    try {
      const resumeId = localStorage.getItem('current_resume_id') || undefined;
      const result = await startInterview(resumeId);
      
      setSessionId(result.sessionId);

      const greetingMessage: InterviewMessage = {
        id: crypto.randomUUID(),
        session_id: result.sessionId,
        role: 'assistant',
        content: result.message,
        created_at: new Date().toISOString()
      };

      setMessages([greetingMessage]);
    } catch (error) {
      console.error('Error starting interview:', error);
      alert('开始面试失败: ' + (error instanceof Error ? error.message : '未知错误'));
      setSessionStarted(false);
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading || !sessionId) return;

    const userMessage: InterviewMessage = {
      id: crypto.randomUUID(),
      session_id: sessionId,
      role: 'user',
      content: inputValue,
      created_at: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    const currentInput = inputValue;
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await simulateInterviewChat(sessionId, currentInput);

      const assistantMessage: InterviewMessage = {
        id: crypto.randomUUID(),
        session_id: sessionId,
        role: 'assistant',
        content: response,
        created_at: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      alert('发送消息失败: ' + (error instanceof Error ? error.message : '未知错误'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {!sessionStarted ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-8rem)]">
            <div className="text-center max-w-2xl">
              <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <Sparkles className="w-10 h-10 text-white" />
              </div>

              <h1 className="text-4xl font-bold text-gray-900 mb-4">AI 智能面试</h1>
              <p className="text-lg text-gray-600 mb-8 leading-relaxed">
                通过 AI 驱动的模拟面试，提升您的面试技巧。系统会根据您的简历信息，
                为您提供针对性的面试问题和专业反馈。
              </p>

              <div className="bg-white rounded-xl shadow-sm p-8 mb-8">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">面试流程</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
                  <div className="flex flex-col">
                    <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-semibold mb-3">
                      1
                    </div>
                    <h3 className="font-medium text-gray-900 mb-2">自我介绍</h3>
                    <p className="text-sm text-gray-600">分享您的背景和工作经验</p>
                  </div>
                  <div className="flex flex-col">
                    <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-semibold mb-3">
                      2
                    </div>
                    <h3 className="font-medium text-gray-900 mb-2">技术问答</h3>
                    <p className="text-sm text-gray-600">回答专业技术相关问题</p>
                  </div>
                  <div className="flex flex-col">
                    <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-semibold mb-3">
                      3
                    </div>
                    <h3 className="font-medium text-gray-900 mb-2">获得反馈</h3>
                    <p className="text-sm text-gray-600">收到详细的面试表现评估</p>
                  </div>
                </div>
              </div>

              <button
                onClick={handleStartInterview}
                className="px-8 py-4 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl hover:from-blue-700 hover:to-blue-800 transition-all font-semibold text-lg shadow-lg hover:shadow-xl"
              >
                开始面试
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col h-[calc(100vh-8rem)]">
            <div className="bg-white rounded-t-xl shadow-sm p-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
                    <Bot className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h2 className="font-semibold text-gray-900">AI 面试官</h2>
                    <p className="text-sm text-gray-600">在线</p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setSessionStarted(false);
                    setMessages([]);
                    setSessionId(null);
                  }}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  结束面试
                </button>
              </div>
            </div>

            <div className="flex-1 bg-gray-50 overflow-y-auto p-6 space-y-4">
              {messages.map(message => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`flex items-start space-x-3 max-w-[80%] ${message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
                    <div className={`
                      w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
                      ${message.role === 'user'
                        ? 'bg-gray-200'
                        : 'bg-gradient-to-br from-blue-500 to-purple-600'
                      }
                    `}>
                      {message.role === 'user' ? (
                        <User className="w-5 h-5 text-gray-700" />
                      ) : (
                        <Bot className="w-5 h-5 text-white" />
                      )}
                    </div>

                    <div
                      className={`
                        px-4 py-3 rounded-2xl
                        ${message.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'bg-white text-gray-900 shadow-sm'
                        }
                      `}
                    >
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
                    </div>
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-start">
                  <div className="flex items-start space-x-3 max-w-[80%]">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-gradient-to-br from-blue-500 to-purple-600">
                      <Bot className="w-5 h-5 text-white" />
                    </div>
                    <div className="bg-white px-4 py-3 rounded-2xl shadow-sm">
                      <div className="flex space-x-2">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
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
                  className="flex-1 resize-none border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
                  style={{ minHeight: '48px', maxHeight: '120px' }}
                />
                <button
                  onClick={sendMessage}
                  disabled={!inputValue.trim() || isLoading}
                  className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
                >
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
