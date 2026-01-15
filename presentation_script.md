# FindBestCareers Presentation Script
**Presenter: HE Yufeng**

---

## [Slide 1 - Title] (15 seconds)

Good afternoon! Have you ever tailored your resume for hours, wondering if you're even qualified? Or faced a generic interview that didn't match your level? 

Well, today we're solving BOTH with **FindBestCareers**—an LLM-powered multi-agent system that's basically your personal AI career advisor. Think Stanford career counselor meets Netflix recommendations!

---

## [Slide 2 - The Problem] (15 seconds)

Here's the thing—traditional career tools are BROKEN. They do keyword matching: "Python" equals match, regardless of whether you've built production systems or just took a class. Interviews are one-size-fits-all. And match scores? Total black box. We fix ALL of that with evidence-based scoring, adaptive interviews, and explainable reasoning.

---

## [Slide 3 - Demo Video] (1 minute)

Now, let me show you how this actually works in the real world.

**[START VIDEO - Narrate while playing]**

"So here's our interface—clean, professional, no nonsense. Watch what happens when I upload my resume..."

*[Video shows resume upload]*

"The system extracts everything automatically—education from Tsinghua, work experience at ByteDance—and here's the cool part: it scores EVERY skill from 1 to 5 using our rigorous V4 scoring framework. Notice how Python gets a 4 because I have multiple production projects, but TensorFlow gets a 3—the AI detected I mostly used it in coursework."

*[Video shows job matching]*

"Now the magic happens—it matches me against real ByteDance positions. See these match scores? The 'LLM Agent Researcher' position shows 87% because my skills overlap perfectly. The system even explains WHY—it's not just keyword matching."

*[Video shows interview simulation]*

"And the best part? Click 'Start Interview' and boom—you get a personalized technical interview. The AI asks progressively harder questions based on your performance, evaluates your answers in real-time, and gives you a comprehensive feedback report. No more generic interview prep—this adapts to YOU."

**[END VIDEO]**

---

## [Slide 4 - Architecture] (20 seconds)

Now let's talk architecture. This isn't a hackathon project—it's **production-grade**. Three specialized agents on Flask: Resume Parser with 2-stage LLM pipeline, Job Matcher with signal detection, and Interview Agent with a 3-phase state machine. All connected through a unified LLM client that supports OpenAI AND DeepSeek, with automatic key rotation across 10+ API keys. Frontend is React with TypeScript for type safety. Modular, scalable, stateful.

---

## [Slide 5 - Evidence-Based Scoring] (25 seconds)

Here's where the research depth shows. We iterated our scoring framework FIVE times to get V4. Every skill score is backed by evidence—"Python 4/5" means production code AND leadership, with citations like "Led team of 5 at ByteDance." No evidence? Score drops to 2 or below—mandatory downgrade rules. This is research-level prompt engineering: structured JSON outputs, strict schemas, robust parsing with 3x retry. We're not just calling GPT and hoping—we're building reliable reasoning.

---

## [Slide 6 - Signal Detection] (25 seconds)

This is where we beat traditional systems. Our Job Signal Analyzer detects five types of intensity signals: PhD requirements, flagship programs, top conferences like NeurIPS, international labs, frontier LLM research. Each has a weight, and the total determines calibration. A standard job might accept Python 3/5, but if it's a research position with NeurIPS publications? The system knows to demand 4 or 5. Dynamic score adjustment—that's semantic understanding, not keyword matching from 2010.

---

## [Slide 7 - Adaptive Interview Agent] (25 seconds)

The Interview Agent is an orchestrator, not just Q&A. It's a three-phase state machine: greeting, technical Q&A with adaptive difficulty, and comprehensive summary. If your average score is 4+, questions get HARDER. If you're at 2, they ease up. It detects shallow answers and asks follow-ups. Real-time evaluation across five dimensions: understanding, logic, feasibility, depth, communication. The final feedback isn't generic—it's specific, actionable improvements. We studied real interview patterns to make this realistic.

---

## [Slide 8 - Team Division] (20 seconds)

Clear division of labor. **Me—HE Yufeng**: I architected all the AI—Resume Parser, Job Matcher, Interview Agent, plus the unified LLM client and that V4 scoring framework we iterated five times. **LIU Jinlin**: Full-stack development—React frontend, Flask backend, state management, made it all work. Together: 80+ hours, 3000+ lines, 5 iterations, tested with real ByteDance job postings, stress-tested with 10+ API keys at scale.

---

## [Slide 9 - Research Impact] (20 seconds)

Why does this matter academically? We're demonstrating **faithful LLM use**—grounded in a 1000+ skill taxonomy, no hallucination, evidence citations. We're showing **production-grade agentic patterns**—state machines, structured outputs, error handling. And we're proving LLMs can be **reliable reasoning engines** for high-stakes decisions like careers, not just chatbots. This is NLP meets HCI meets Software Engineering—explainable AI, adaptive UX, semantic matching.

---

## [Slide 10 - Closing] (15 seconds)

To recap: We built an AI career advisor that understands your skills through evidence-based scoring, matches you to jobs with signal detection and reasoning, and prepares you with adaptive interviews and real feedback. 80+ hours, 3000+ lines, 5 iterations. We demonstrated faithful LLM use, production-grade multi-agent systems, and explainable AI for career decisions.

Questions? We're ready—or better yet, let our AI interview YOU!

Thank you!

---

---

## **Time Breakdown:**
- Slide 1: 15s
- Slide 2: 15s
- Slide 3 (Video): 60s
- Slide 4: 20s
- Slide 5: 25s
- Slide 6: 25s
- Slide 7: 25s
- Slide 8: 20s
- Slide 9: 20s
- Slide 10: 15s

**Total: 240 seconds = 4 minutes exactly** ✅

**Speaking Word Count: ~420 words** (excluding video narration, at ~105 words/minute conversational pace)

