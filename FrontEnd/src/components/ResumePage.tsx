import { useState } from 'react';
import { Upload, FileText, Loader, Star, Award, TrendingUp } from 'lucide-react';
import { Resume, ResumeSkill } from '../types';
import { simulateResumeUpload } from '../lib/mockApi';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer } from 'recharts';

interface ResumePageProps {
  resume: Resume | null;
  skills: ResumeSkill[];
  onResumeChange: (resume: Resume | null) => void;
  onSkillsChange: (skills: ResumeSkill[]) => void;
}

export default function ResumePage({ resume, skills, onResumeChange, onSkillsChange }: ResumePageProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadProgress(0);

    // Simulate progress
    const progressInterval = setInterval(() => {
      setUploadProgress(prev => Math.min(prev + Math.random() * 15, 90));
    }, 500);

    try {
      const result = await simulateResumeUpload(file);
      clearInterval(progressInterval);
      setUploadProgress(100);
      onResumeChange(result.resume);
      onSkillsChange(result.skills);
      localStorage.setItem('current_resume_id', result.resume.id);
    } catch (error) {
      clearInterval(progressInterval);
      console.error('Upload failed:', error);
      alert('上传失败: ' + (error instanceof Error ? error.message : '未知错误'));
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const renderStars = (score: number) => (
    <div className="flex space-x-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <Star
          key={i}
          className={`w-4 h-4 ${i <= score ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'}`}
        />
      ))}
    </div>
  );

  const renderScoreBar = (score: number) => {
    const colors = ['', 'bg-red-400', 'bg-orange-400', 'bg-yellow-400', 'bg-blue-500', 'bg-green-500'];
    return (
      <div className="flex items-center space-x-2 flex-1 max-w-[140px]">
        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${colors[score] || 'bg-gray-300'}`}
            style={{ width: `${(score / 5) * 100}%` }}
          />
        </div>
        <span className="text-xs font-bold text-gray-500 w-6">{score}/5</span>
      </div>
    );
  };

  const groupedSkills = skills.reduce((acc, skill) => {
    if (!acc[skill.category]) acc[skill.category] = [];
    acc[skill.category].push(skill);
    return acc;
  }, {} as Record<string, ResumeSkill[]>);

  const orderedCategories = Object.keys(groupedSkills).sort((a, b) => {
    if (a === '其他') return 1;
    if (b === '其他') return -1;
    return a.localeCompare(b);
  });

  // Radar chart data: if enough categories, use category averages; otherwise use top individual skills
  let radarData: { category: string; score: number; fullMark: number }[] = [];
  const nonOtherCategories = orderedCategories.filter(c => c !== '其他');
  if (nonOtherCategories.length >= 3) {
    radarData = nonOtherCategories.slice(0, 8).map(category => {
      const catSkills = groupedSkills[category];
      const avg = catSkills.reduce((sum, s) => sum + s.score, 0) / catSkills.length;
      return { category: category.length > 6 ? category.slice(0, 6) + '..' : category, score: Math.round(avg * 10) / 10, fullMark: 5 };
    });
  } else if (skills.length >= 3) {
    // Fallback: use top individual skills for radar
    radarData = [...skills].sort((a, b) => b.score - a.score).slice(0, 8).map(s => ({
      category: s.skill_name.length > 6 ? s.skill_name.slice(0, 6) + '..' : s.skill_name,
      score: s.score,
      fullMark: 5
    }));
  }

  // Stats
  const avgScore = skills.length > 0 ? (skills.reduce((s, sk) => s + sk.score, 0) / skills.length).toFixed(1) : '0';
  const topSkills = [...skills].sort((a, b) => b.score - a.score).slice(0, 3);

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {!resume ? (
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold text-gray-900 mb-2">上传简历</h1>
              <p className="text-gray-600">支持 PDF 格式，系统将自动提取并分析您的简历信息</p>
            </div>

            <div className="bg-white rounded-xl shadow-sm border-2 border-dashed border-gray-300 hover:border-blue-400 transition-colors">
              <label className="block cursor-pointer">
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleFileUpload}
                  disabled={uploading}
                  className="hidden"
                />
                <div className="p-12 text-center">
                  {uploading ? (
                    <div className="flex flex-col items-center">
                      <Loader className="w-12 h-12 text-blue-500 animate-spin mb-4" />
                      <p className="text-gray-700 font-medium">AI 正在分析您的简历...</p>
                      <div className="w-64 h-2 bg-gray-200 rounded-full mt-4 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-300"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                      <p className="text-gray-500 text-sm mt-2">正在提取信息并评估技能...</p>
                    </div>
                  ) : (
                    <>
                      <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                      <p className="text-gray-700 font-medium mb-1">点击上传或拖拽文件至此</p>
                      <p className="text-gray-500 text-sm">仅支持 PDF 格式，文件大小不超过 10MB</p>
                    </>
                  )}
                </div>
              </label>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">简历分析结果</h1>
                <p className="text-gray-600 mt-1">文件名：{resume.file_name}</p>
              </div>
              <button
                onClick={() => { onResumeChange(null); onSkillsChange([]); }}
                className="px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-gray-700 font-medium"
              >
                上传新简历
              </button>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-4 text-white">
                <p className="text-blue-100 text-sm">综合评分</p>
                <p className="text-3xl font-bold mt-1">{avgScore}<span className="text-lg text-blue-200">/5</span></p>
              </div>
              <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-4 text-white">
                <p className="text-purple-100 text-sm">评估技能数</p>
                <p className="text-3xl font-bold mt-1">{skills.length}</p>
              </div>
              <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-xl p-4 text-white">
                <p className="text-green-100 text-sm">最强技能</p>
                <p className="text-lg font-bold mt-1 truncate">{topSkills[0]?.skill_name || '-'}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left: Basic Info */}
              <div className="bg-white rounded-xl shadow-sm p-6 space-y-6">
                <div className="flex items-center space-x-2 mb-4">
                  <FileText className="w-5 h-5 text-blue-600" />
                  <h2 className="text-xl font-semibold text-gray-900">基本信息</h2>
                </div>

                <div className="space-y-4">
                  {[
                    ['姓名', resume.extracted_info.name],
                    ['邮箱', resume.extracted_info.email],
                    ['电话', resume.extracted_info.phone],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <label className="text-sm font-medium text-gray-500">{label}</label>
                      <p className="text-gray-900 mt-1">{value || '-'}</p>
                    </div>
                  ))}
                </div>

                <div className="pt-4 border-t border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">教育背景</h3>
                  <div className="space-y-3">
                    {resume.extracted_info.education?.map((edu, i) => (
                      <div key={i} className="bg-gray-50 rounded-lg p-3">
                        <p className="font-medium text-gray-900 text-sm">{edu.school}</p>
                        <p className="text-gray-600 text-xs mt-1">{edu.degree} · {edu.major} · {edu.year}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-4 border-t border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">工作经历</h3>
                  <div className="space-y-3">
                    {resume.extracted_info.experience?.map((exp, i) => (
                      <div key={i} className="bg-gray-50 rounded-lg p-3">
                        <p className="font-medium text-gray-900 text-sm">{exp.company}</p>
                        <p className="text-gray-600 text-xs">{exp.position} · {exp.duration}</p>
                        {exp.description && <p className="text-gray-500 text-xs mt-1 line-clamp-2">{exp.description}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Center: Radar Chart */}
              <div className="bg-white rounded-xl shadow-sm p-6">
                <div className="flex items-center space-x-2 mb-4">
                  <TrendingUp className="w-5 h-5 text-blue-600" />
                  <h2 className="text-xl font-semibold text-gray-900">能力画像</h2>
                </div>

                {radarData.length >= 3 ? (
                  <ResponsiveContainer width="100%" height={280}>
                    <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                      <PolarGrid stroke="#e5e7eb" />
                      <PolarAngleAxis dataKey="category" tick={{ fontSize: 11, fill: '#6b7280' }} />
                      <PolarRadiusAxis angle={90} domain={[0, 5]} tick={{ fontSize: 10, fill: '#9ca3af' }} />
                      <Radar name="技能" dataKey="score" stroke="#6366f1" fill="#6366f1" fillOpacity={0.25} strokeWidth={2} />
                    </RadarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[280px] flex items-center justify-center text-gray-400 text-sm">
                    技能数据不足，无法生成雷达图
                  </div>
                )}

                {/* Top skills highlight */}
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <h4 className="text-sm font-semibold text-gray-700 mb-3">核心优势技能</h4>
                  <div className="space-y-2">
                    {topSkills.map((skill, i) => (
                      <div key={skill.id} className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white ${
                            i === 0 ? 'bg-yellow-500' : i === 1 ? 'bg-gray-400' : 'bg-amber-700'
                          }`}>{i + 1}</span>
                          <span className="text-sm font-medium text-gray-900">{skill.skill_name}</span>
                        </div>
                        {renderStars(skill.score)}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right: All Skills */}
              <div className="bg-white rounded-xl shadow-sm p-6">
                <div className="flex items-center space-x-2 mb-6">
                  <Award className="w-5 h-5 text-blue-600" />
                  <h2 className="text-xl font-semibold text-gray-900">技能详情</h2>
                </div>

                <div className="space-y-5 max-h-[600px] overflow-y-auto pr-2">
                  {orderedCategories.map((category) => {
                    const categorySkills = groupedSkills[category];
                    return (
                      <div key={category}>
                        <h3 className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">
                          {category}
                        </h3>
                        <div className="space-y-2">
                          {categorySkills.map(skill => (
                            <div key={skill.id} className="flex items-center justify-between py-1">
                              <span className="text-sm text-gray-800">{skill.skill_name}</span>
                              {renderScoreBar(skill.score)}
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
