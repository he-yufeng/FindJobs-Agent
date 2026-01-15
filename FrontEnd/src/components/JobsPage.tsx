import { useState, useEffect } from 'react';
import { Search, MapPin, DollarSign, TrendingUp, CheckCircle2, ChevronLeft, ChevronRight } from 'lucide-react';
import { JobPosition } from '../types';
import { getJobs, simulateJobMatching } from '../lib/mockApi';

const ITEMS_PER_PAGE = 4;

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobPosition[]>([]);
  const [filteredJobs, setFilteredJobs] = useState<JobPosition[]>([]);
  const [selectedKeywords, setSelectedKeywords] = useState<string[]>([]);
  const [availableKeywords, setAvailableKeywords] = useState<string[]>([]);
  const [showAllKeywords, setShowAllKeywords] = useState(false);
  const [matchScores, setMatchScores] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [resumeId, setResumeId] = useState<string | null>(null);

  useEffect(() => {
    // 从localStorage获取resume_id
    const savedResumeId = localStorage.getItem('current_resume_id');
    if (savedResumeId) {
      setResumeId(savedResumeId);
    }
    loadJobs();
  }, []);

  useEffect(() => {
    // 使用当前的matchScores进行排序
    applyFiltersAndSort(jobs, matchScores);
  }, [jobs, selectedKeywords, searchQuery, matchScores]);

  useEffect(() => {
    if (resumeId && jobs.length > 0) {
      loadMatchScores();
    }
  }, [resumeId, jobs]);

  const loadJobs = async () => {
    try {
      const jobsData = await getJobs();
      setJobs(jobsData);
      setFilteredJobs(jobsData);

      // 统计每个技能在所有岗位中出现的频率
      const skillCountMap = new Map<string, number>();
      jobsData.forEach(job => {
        job.required_skills.forEach(skill => {
          const trimmed = skill.trim();
          if (trimmed) {
            skillCountMap.set(trimmed, (skillCountMap.get(trimmed) || 0) + 1);
          }
        });
      });
      // 按频率降序排序，只取前50个高频技能
      const skillsArray = Array.from(skillCountMap.entries())
        .sort((a, b) => b[1] - a[1]) // 按频率降序
        .slice(0, 50)
        .map(([skill]) => skill); // 只取技能名
      setAvailableKeywords(skillsArray);
    } catch (error) {
      console.error('Error loading jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMatchScores = async () => {
    if (!resumeId) return;
    
    try {
      const matches = await simulateJobMatching(resumeId);
      const scoreMap: Record<string, number> = {};
      const matchDetailsMap: Record<string, any> = {};
      
      matches.forEach(match => {
        scoreMap[match.job_id] = match.match_score;
        matchDetailsMap[match.job_id] = {
          match_count: match.match_details?.match_count || 0,
          matched_skills: match.matched_skills || []
        };
      });
      
      setMatchScores(scoreMap);
      
      // 按照匹配度排序：优先匹配标签数量，其次匹配分数
      const sortedJobs = [...jobs].sort((a, b) => {
        const scoreA = scoreMap[a.id] || 0;
        const scoreB = scoreMap[b.id] || 0;
        const matchCountA = matchDetailsMap[a.id]?.match_count || 0;
        const matchCountB = matchDetailsMap[b.id]?.match_count || 0;
        
        // 优先按匹配标签数量排序（降序）
        if (matchCountA !== matchCountB) {
          return matchCountB - matchCountA;
        }
        // 其次按匹配分数排序（降序）
        return scoreB - scoreA;
      });
      
      setJobs(sortedJobs);
      
      // 重新应用筛选和排序
      applyFiltersAndSort(sortedJobs, scoreMap);
    } catch (error) {
      console.error('Error loading match scores:', error);
    }
  };
  
  const applyFiltersAndSort = (jobsToFilter: JobPosition[], scores: Record<string, number>) => {
    let filtered = jobsToFilter;

    if (selectedKeywords.length > 0) {
      filtered = filtered.filter(job =>
        selectedKeywords.every(keyword =>
          job.required_skills.some(skill =>
            skill.toLowerCase().includes(keyword.toLowerCase())
          )
        )
      );
    }

    if (searchQuery) {
      filtered = filtered.filter(job =>
        job.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        job.company.toLowerCase().includes(searchQuery.toLowerCase()) ||
        job.description.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    
    // 按照匹配度排序：按匹配分数排序（降序）
    filtered = filtered.sort((a, b) => {
      const scoreA = scores[a.id] || 0;
      const scoreB = scores[b.id] || 0;
      
      // 如果没有匹配分数，保持原顺序
      if (scoreA === 0 && scoreB === 0) {
        return 0;
      }
      
      // 按匹配分数排序（降序）
      return scoreB - scoreA;
    });

    setFilteredJobs(filtered);
  };


  const toggleKeyword = (keyword: string) => {
    setSelectedKeywords(prev =>
      prev.includes(keyword)
        ? prev.filter(k => k !== keyword)
        : [...prev, keyword]
    );
  };

  const totalPages = Math.ceil(filteredJobs.length / ITEMS_PER_PAGE);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const paginatedJobs = filteredJobs.slice(startIndex, startIndex + ITEMS_PER_PAGE);

  // 生成智能分页显示的页码数组
  const getDisplayPages = (): (number | string)[] => {
    if (totalPages <= 7) {
      // 如果总页数少于等于7，显示所有页码
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }

    const pages: (number | string)[] = [];
    const delta = 2; // 当前页前后各显示2页

    // 总是显示第一页
    pages.push(1);

    // 计算当前页附近的页码范围
    const start = Math.max(2, currentPage - delta);
    const end = Math.min(totalPages - 1, currentPage + delta);

    // 如果第一页和当前页附近有间隔，添加省略号
    if (start > 2) {
      pages.push('...');
    }

    // 添加当前页附近的页码
    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    // 如果当前页附近和最后一页有间隔，添加省略号
    if (end < totalPages - 1) {
      pages.push('...');
    }

    // 总是显示最后一页（如果总页数大于1）
    if (totalPages > 1) {
      pages.push(totalPages);
    }

    return pages;
  };

  const displayPages = getDisplayPages();

  const getMatchColor = (score: number) => {
    if (score >= 90) return 'text-green-600 bg-green-50';
    if (score >= 75) return 'text-blue-600 bg-blue-50';
    if (score >= 60) return 'text-yellow-600 bg-yellow-50';
    return 'text-gray-600 bg-gray-50';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">加载岗位信息...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">岗位匹配</h1>
          <p className="text-gray-600">根据您的技能和偏好，为您推荐最合适的岗位</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">搜索岗位</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="搜索职位名称、公司或描述..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">筛选技能关键词</label>
            <div className="flex flex-wrap gap-2">
            {(
              showAllKeywords
                ? availableKeywords
                : availableKeywords.slice(0, 12)
            ).map(keyword => {
              const isSelected = selectedKeywords.includes(keyword);
                return (
                  <button
                  key={keyword}
                  onClick={() => toggleKeyword(keyword)}
                    className={`
                      px-4 py-2 rounded-full text-sm font-medium transition-all
                      ${isSelected
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }
                    `}
                  >
                    {isSelected && <CheckCircle2 className="inline w-4 h-4 mr-1" />}
                    {keyword}
                  </button>
                );
              })}
            </div>
            <div className="mt-3 flex gap-4">
              {availableKeywords.length > 12 && (
                <button
                  onClick={() => setShowAllKeywords(prev => !prev)}
                  className="text-sm text-blue-600 hover:text-blue-700 font-medium"
                >
                  {showAllKeywords ? '收起关键词' : `展开更多关键词（共 ${availableKeywords.length} 个）`}
                </button>
              )}
              {selectedKeywords.length > 0 && (
                <button
                  onClick={() => setSelectedKeywords([])}
                  className="text-sm text-blue-600 hover:text-blue-700 font-medium"
                >
                  清除所有筛选
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="mb-4 flex items-center justify-between">
          <p className="text-gray-600">
            找到 <span className="font-semibold text-gray-900">{filteredJobs.length}</span> 个匹配岗位
          </p>
        </div>

        <div className="space-y-4 mb-6">
          {paginatedJobs.map(job => {
            const matchScore = matchScores[job.id] || 0;
            return (
              <div key={job.id} className="bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <h3 className="text-xl font-semibold text-gray-900">{job.title}</h3>
                      <div className={`px-3 py-1 rounded-full text-sm font-semibold ${getMatchColor(matchScore)}`}>
                        <TrendingUp className="inline w-4 h-4 mr-1" />
                        匹配度 {matchScore}%
                      </div>
                    </div>
                    <p className="text-lg text-gray-700 font-medium">{job.company}</p>
                  </div>
                </div>

                <p className="text-gray-600 mb-4 leading-relaxed">{job.description}</p>

                <div className="flex flex-wrap items-center gap-4 mb-4 text-sm text-gray-600">
                  <div className="flex items-center space-x-1">
                    <MapPin className="w-4 h-4" />
                    <span>{job.location}</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <DollarSign className="w-4 h-4" />
                    <span>{job.salary_range}</span>
                  </div>
                </div>

                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">技能要求：</p>
                  <div className="flex flex-wrap gap-2">
                    {job.required_skills.map((skill, index) => (
                      <span
                        key={index}
                        className={`
                          px-3 py-1 rounded-full text-sm
                          ${selectedKeywords.some(k => skill.toLowerCase().includes(k.toLowerCase()))
                            ? 'bg-blue-100 text-blue-700 font-medium'
                            : 'bg-gray-100 text-gray-700'
                          }
                        `}
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-gray-200">
                  <button
                    className="w-full sm:w-auto px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={!job.apply_url}
                    onClick={() => {
                      if (job.apply_url) {
                        window.open(job.apply_url, '_blank', 'noopener,noreferrer');
                      }
                    }}
                  >
                    申请职位
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-center space-x-2">
            <button
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
              className="p-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>

            <div className="flex space-x-1">
              {displayPages.map((page, index) => {
                if (page === '...') {
                  return (
                    <span
                      key={`ellipsis-${index}`}
                      className="px-2 text-gray-500"
                    >
                      ...
                    </span>
                  );
                }
                return (
                  <button
                    key={page}
                    onClick={() => setCurrentPage(page as number)}
                    className={`
                      w-10 h-10 rounded-lg font-medium transition-colors
                      ${currentPage === page
                        ? 'bg-blue-600 text-white'
                        : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                      }
                    `}
                  >
                    {page}
                  </button>
                );
              })}
            </div>

            <button
              onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
              className="p-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        )}

        {filteredJobs.length === 0 && (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center">
            <Search className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">未找到匹配的岗位</h3>
            <p className="text-gray-600">尝试调整您的筛选条件或搜索关键词</p>
          </div>
        )}
      </div>
    </div>
  );
}
