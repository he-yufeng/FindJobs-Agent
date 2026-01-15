import { useState } from 'react';
import { Upload, FileText, Loader, Star, Award } from 'lucide-react';
import { Resume, ResumeSkill } from '../types';
import { simulateResumeUpload } from '../lib/mockApi';

export default function ResumePage() {
  const [uploading, setUploading] = useState(false);
  const [resume, setResume] = useState<Resume | null>(null);
  const [skills, setSkills] = useState<ResumeSkill[]>([]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);

    try {
      const result = await simulateResumeUpload(file);
      setResume(result.resume);
      setSkills(result.skills);
      // 保存resume_id到localStorage，供岗位匹配使用
      localStorage.setItem('current_resume_id', result.resume.id);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('上传失败: ' + (error instanceof Error ? error.message : '未知错误'));
    } finally {
      setUploading(false);
    }
  };

  const renderStars = (score: number) => {
    return (
      <div className="flex space-x-0.5">
        {[1, 2, 3, 4, 5].map(i => (
          <Star
            key={i}
            className={`w-4 h-4 ${i <= score ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'}`}
          />
        ))}
      </div>
    );
  };

  const groupedSkills = skills.reduce((acc, skill) => {
    if (!acc[skill.category]) {
      acc[skill.category] = [];
    }
    acc[skill.category].push(skill);
    return acc;
  }, {} as Record<string, ResumeSkill[]>);

  // 将“其他”类别排在最后
  const orderedCategories = Object.keys(groupedSkills).sort((a, b) => {
    const aIsOther = a === '其他';
    const bIsOther = b === '其他';
    if (aIsOther && !bIsOther) return 1;
    if (!aIsOther && bIsOther) return -1;
    return a.localeCompare(b);
  });

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
                      <p className="text-gray-700 font-medium">正在分析简历...</p>
                      <p className="text-gray-500 text-sm mt-2">这可能需要几秒钟</p>
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
                onClick={() => {
                  setResume(null);
                  setSkills([]);
                }}
                className="px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-gray-700 font-medium"
              >
                上传新简历
              </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white rounded-xl shadow-sm p-6 space-y-6">
                <div className="flex items-center space-x-2 mb-4">
                  <FileText className="w-5 h-5 text-blue-600" />
                  <h2 className="text-xl font-semibold text-gray-900">基本信息</h2>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-medium text-gray-500">姓名</label>
                    <p className="text-gray-900 mt-1">{resume.extracted_info.name}</p>
                  </div>

                  <div>
                    <label className="text-sm font-medium text-gray-500">邮箱</label>
                    <p className="text-gray-900 mt-1">{resume.extracted_info.email}</p>
                  </div>

                  <div>
                    <label className="text-sm font-medium text-gray-500">电话</label>
                    <p className="text-gray-900 mt-1">{resume.extracted_info.phone}</p>
                  </div>
                </div>

                <div className="pt-4 border-t border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">教育背景</h3>
                  <div className="space-y-4">
                    {resume.extracted_info.education?.map((edu, index) => (
                      <div key={index} className="bg-gray-50 rounded-lg p-4">
                        <p className="font-medium text-gray-900">{edu.school}</p>
                        <p className="text-gray-700 text-sm mt-1">
                          {edu.degree} · {edu.major}
                        </p>
                        <p className="text-gray-500 text-sm mt-1">{edu.year}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-4 border-t border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">工作经历</h3>
                  <div className="space-y-4">
                    {resume.extracted_info.experience?.map((exp, index) => (
                      <div key={index} className="bg-gray-50 rounded-lg p-4">
                        <p className="font-medium text-gray-900">{exp.company}</p>
                        <p className="text-gray-700 text-sm mt-1">{exp.position}</p>
                        <p className="text-gray-500 text-sm mt-1">{exp.duration}</p>
                        <p className="text-gray-600 text-sm mt-2">{exp.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl shadow-sm p-6">
                <div className="flex items-center space-x-2 mb-6">
                  <Award className="w-5 h-5 text-blue-600" />
                  <h2 className="text-xl font-semibold text-gray-900">技能评估</h2>
                </div>

                <div className="space-y-6">
                  {orderedCategories.map((category) => {
                    const categorySkills = groupedSkills[category];
                    return (
                    <div key={category}>
                      <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
                        {category}
                      </h3>
                      <div className="space-y-3">
                        {categorySkills.map(skill => (
                          <div key={skill.id} className="flex items-center justify-between py-2">
                            <span className="text-gray-900 font-medium">{skill.skill_name}</span>
                            <div className="flex items-center space-x-3">
                              {renderStars(skill.score)}
                              <span className="text-sm font-semibold text-gray-600 w-8 text-right">
                                {skill.score}/5
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )})}
                </div>

                <div className="mt-8 pt-6 border-t border-gray-200">
                  <div className="bg-blue-50 rounded-lg p-4">
                    <p className="text-sm font-medium text-blue-900 mb-2">综合评价</p>
                    <p className="text-sm text-blue-700">
                      您的技能组合非常全面，特别是在算法和机器学习方向表现出色。
                      建议继续深化在深度学习领域的实践经验。
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
