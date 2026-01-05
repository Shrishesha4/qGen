<script>
  import { authState } from "../stores/auth";
  import { navigate } from "../stores/router";
  import { onMount } from "svelte";
  import { jsPDF } from "jspdf";
  import { API_URL } from "../config/api";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Label } from "$lib/components/ui/label";
  import { Textarea } from "$lib/components/ui/textarea";
  import { Select } from "$lib/components/ui/select";
  import { Card, CardContent, CardHeader, CardTitle } from "$lib/components/ui/card";

  let token;
  authState.subscribe(v => token = v.token);

  let topic = "";
  let content = "";
  let numQuestions = 5;
  let numSets = 1;
  let difficulty = "medium";
  let questionType = "multiple_choice";
  let userContext = "";
  let useWebSearch = false;
  let files;
  
  let questionSets = [];
  let loading = false;
  let error = null;
  let progressMessage = "";
  let currentStep = "";
  let totalSets = 0;
  let completedSets = 0;
  
  // Export state
  let expandedExports = {
    all: false,
    sets: {}
  };
  
  // Collapsible state for sets and questions
  let collapsedSets = {};
  let collapsedQuestions = {};
  
  // Regeneration loading state
  let regeneratingQuestionId = null;
  
  // LLM thinking text
  let thinkingText = "";
  let generationThinkingText = "";
  let validationThinkingText = "";
  
  // Validation modal state
  let showValidationModal = false;
  let currentSetValidationThinking = "";
  
  // Thinking box scroll reference
  let thinkingBoxEl;

  // Format validation text for display
  function formatValidationText(text) {
    if (!text) return '';
    
    // Try to parse as JSON (old format - shouldn't happen with new validator)
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed)) {
        // Format each question nicely
        return parsed.map((q, idx) => {
          let formatted = `Question ${idx + 1}:\n`;
          formatted += `  ${q.description}\n\n`;
          formatted += `  Options:\n`;
          q.options.forEach((opt, i) => {
            const letter = String.fromCharCode(65 + i);
            const marker = opt === q.answer ? ' ✓ (Correct)' : '';
            formatted += `    ${letter}. ${opt}${marker}\n`;
          });
          if (q.explanation) {
            formatted += `\n  Explanation:\n    ${q.explanation}\n`;
          }
          return formatted;
        }).join('\n' + '='.repeat(80) + '\n\n');
      }
      // If it's an object, pretty print it
      return JSON.stringify(parsed, null, 2);
    } catch (e) {
      // Not JSON - this is the natural language validation report
      // Just return it as is (already formatted nicely by the LLM)
      return text;
    }
  }

  // Auto-scroll thinking box to bottom slowly
  $: if (thinkingBoxEl && thinkingText) {
    setTimeout(() => {
      if (thinkingBoxEl) {
        thinkingBoxEl.scrollTo({
          top: thinkingBoxEl.scrollHeight,
          behavior: 'smooth'
        });
      }
    }, 50);
  }

  // Persist question sets to localStorage
  function saveToLocalStorage() {
    if (questionSets.length > 0) {
      const data = {
        questionSets,
        topic,
        difficulty,
        questionType,
        numQuestions,
        numSets
      };
      localStorage.setItem('dashboardQuestionSets', JSON.stringify(data));
    }
  }

  // Restore from localStorage
  function restoreFromLocalStorage() {
    const saved = localStorage.getItem('dashboardQuestionSets');
    if (saved) {
      try {
        const data = JSON.parse(saved);
        questionSets = data.questionSets || [];
        topic = data.topic || "";
        difficulty = data.difficulty || "medium";
        questionType = data.questionType || "multiple_choice";
        numQuestions = data.numQuestions || 5;
        numSets = data.numSets || 1;
      } catch (e) {
        console.error('Failed to restore from localStorage:', e);
      }
    }
  }

  // Clear localStorage when starting new generation
  function clearLocalStorage() {
    localStorage.removeItem('dashboardQuestionSets');
  }

  // Clear all data including form fields
  function clearAllData() {
    localStorage.removeItem('dashboardQuestionSets');
    questionSets = [];
    topic = "";
    content = "";
    numQuestions = 5;
    numSets = 1;
    difficulty = "medium";
    questionType = "multiple_choice";
    userContext = "";
    useWebSearch = false;
    files = null;
    error = null;
    // Reset file input
    const fileInput = document.getElementById('file');
    if (fileInput instanceof HTMLInputElement) fileInput.value = '';
  }

  // Task-related state
  let currentTaskId = null;
  let currentSessionId = null;

  onMount(() => {
    if (!token) {
      navigate("/login");
      return;
    }

    // Check if navigated with task data
    if (history.state && history.state.taskId) {
      const state = history.state;
      currentTaskId = state.taskId;
      topic = state.topic || "";
      numQuestions = state.numQuestions || 5;
      numSets = state.numSets || 1;
      difficulty = state.difficulty || "medium";
      questionType = state.questionType || "multiple_choice";
      userContext = state.userContext || "";
      history.replaceState({}, null);
    } else if (history.state && history.state.regenerationData) {
      const data = history.state.regenerationData;
      topic = data.topic;
      numQuestions = data.num_questions;
      numSets = 1;
      difficulty = data.difficulty;
      questionType = data.question_type;
      content = data.generation_config?.content_context || "";
      userContext = data.generation_config?.user_context || "";
      
      history.replaceState({}, null); 
      generateQuestions();
    } else {
      // Restore previous generation if available
      restoreFromLocalStorage();
    }
  });

  // Save to localStorage whenever questionSets changes (but not during load)
  $: if (questionSets.length > 0 && !loading) {
    saveToLocalStorage();
  }

  async function generateQuestions(e) {
    if (e) e.preventDefault();
    if (!topic.trim()) {
      error = "Please enter a topic";
      return;
    }
    
    // Clear previous results from localStorage
    clearLocalStorage();
    
    loading = true;
    error = null;
    questionSets = [];
    progressMessage = "Starting generation...";
    currentStep = "";
    totalSets = numSets;
    completedSets = 0;
    thinkingText = "";
    currentSessionId = null;
    
    try {
      const formData = new FormData();
      formData.append('topic', topic);
      formData.append('num_questions', String(numQuestions));
      formData.append('num_sets', String(numSets));
      formData.append('difficulty', difficulty);
      formData.append('question_type', questionType);
      formData.append('use_web_search', String(useWebSearch));
      if (content) formData.append('content', content);
      if (userContext) formData.append('user_context', userContext);
      if (files && files[0]) formData.append('file', files[0]);
      if (currentTaskId) formData.append('task_id', String(currentTaskId));

      const response = await fetch(`${API_URL}/generate`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: formData,
      });

      if (!response.ok) throw new Error(response.statusText);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop(); 
        
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.replace("data: ", ""));
              // console.log("Received event:", event);
              
              if (event.type === "session") {
                currentSessionId = event.session_id;
              } else if (event.type === "start") {
                totalSets = event.total_sets;
                progressMessage = `Preparing to generate ${event.total_sets} set(s)...`;
                generationThinkingText = "";
                validationThinkingText = "";
              } else if (event.type === "thinking") {
                generationThinkingText += event.text;
                thinkingText = generationThinkingText + validationThinkingText;
              } else if (event.type === "validating") {
                validationThinkingText += event.text;
                thinkingText = generationThinkingText + validationThinkingText;
              } else if (event.type === "progress") {
                currentStep = event.step;
                progressMessage = event.message;
              } else if (event.type === "result") {
                completedSets += 1;
                questionSets = [...questionSets, event.data];
                progressMessage = `Completed set ${completedSets}/${totalSets}`;
                currentSetValidationThinking = validationThinkingText;
                generationThinkingText = "";
                validationThinkingText = "";
                thinkingText = "";
              } else if (event.type === "error") {
                error = event.message;
              } else if (event.type === "complete") {
                progressMessage = "Complete!";
                thinkingText = "";
                // Trigger stats refresh
                window.dispatchEvent(new CustomEvent('statsUpdate'));
                // Clear task after successful completion
                if (currentTaskId) {
                  currentTaskId = null;
                }
              }
            } catch (e) {
              console.error("Parse error:", e, "Line:", line);
            }
          }
        }
      }
    } catch (e) { 
      error = e.message; 
    } finally { 
      loading = false;
      setTimeout(() => {
        progressMessage = "";
      }, 1000);
    }
  }

  async function exportSet(setId, format) {
    try {
      const res = await fetch(`${API_URL}/export/${setId}?format=${format}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `set_${setId}.${format}`;
      a.click();
    } catch (e) { alert(e.message); }
  }

  async function regenerateQuestion(qId, setIndex, qIndex) {
    try {
      regeneratingQuestionId = qId;
      const res = await fetch(`${API_URL}/regenerate/${qId}`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Regeneration failed");
      const newQ = await res.json();
      
      const newSets = [...questionSets];
      newSets[setIndex][qIndex] = newQ;
      questionSets = newSets;
    } catch (e) { alert(e.message); }
    finally {
      regeneratingQuestionId = null;
    }
  }

  function downloadAllAsJSON() {
    const data = {
      topic,
      difficulty,
      questionType,
      totalSets: questionSets.length,
      totalQuestions: questionSets.reduce((sum, set) => sum + set.length, 0),
      sets: questionSets
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    downloadFile(blob, `${topic.replace(/\s+/g, '_')}_all_sets.json`);
  }

  function downloadAllAsCSV() {
    let csv = 'Set,Question Number,Question,Option A,Option B,Option C,Option D,Correct Answer,Explanation\n';
    questionSets.forEach((set, setIdx) => {
      set.forEach((q, qIdx) => {
        const options = q.options.slice(0, 4).concat(Array(4).fill('')).slice(0, 4);
        csv += `${setIdx + 1},${qIdx + 1},"${q.description.replace(/"/g, '""')}","${options[0] ? options[0].replace(/"/g, '""') : ''}","${options[1] ? options[1].replace(/"/g, '""') : ''}","${options[2] ? options[2].replace(/"/g, '""') : ''}","${options[3] ? options[3].replace(/"/g, '""') : ''}","${q.answer.replace(/"/g, '""')}","${(q.explanation || '').replace(/"/g, '""')}"\n`;
      });
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    downloadFile(blob, `${topic.replace(/\s+/g, '_')}_all_sets.csv`);
  }

  function downloadQuestionsOnly() {
    let content = `# Questions for ${topic}\n\n`;
    questionSets.forEach((set, setIdx) => {
      content += `## Set ${setIdx + 1}\n\n`;
      set.forEach((q, qIdx) => {
        content += `### Q${qIdx + 1}: ${q.description}\n\n`;
        q.options.forEach((opt, oIdx) => {
          content += `${String.fromCharCode(65 + oIdx)}. ${opt}\n`;
        });
        content += `\n**Answer:** ${q.answer}\n`;
        if (q.explanation) {
          content += `**Explanation:** ${q.explanation}\n`;
        }
        content += '\n---\n\n';
      });
    });
    const blob = new Blob([content], { type: 'text/markdown' });
    downloadFile(blob, `${topic.replace(/\s+/g, '_')}_questions_only.md`);
  }

  function downloadFile(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
  }

  function downloadAllAsText() {
    let content = `# Question Bank Export\n\n`;
    questionSets.forEach((set, setIdx) => {
      content += `## Set ${setIdx + 1} - ${topic}\n\n`;
      set.forEach((q, qIdx) => {
        content += `### Q${qIdx + 1}: ${q.description}\n\n`;
        q.options.forEach((opt, oIdx) => {
          content += `${String.fromCharCode(65 + oIdx)}. ${opt}\n`;
        });
        content += `\n**Answer:** ${q.answer}\n`;
        if (q.explanation) {
          content += `**Explanation:** ${q.explanation}\n`;
        }
        content += '\n---\n\n';
      });
    });
    const blob = new Blob([content], { type: 'text/plain' });
    downloadFile(blob, `${topic.replace(/\s+/g, '_')}_all_sets.txt`);
  }

  function toggleExportAll() {
    expandedExports.all = !expandedExports.all;
  }

  function toggleExportSet(setIdx) {
    if (!expandedExports.sets[setIdx]) {
      expandedExports.sets[setIdx] = { all: false, questionsOnly: false };
    }
  }

  function toggleExportSetAll(setIdx) {
    if (!expandedExports.sets[setIdx]) {
      expandedExports.sets[setIdx] = { all: false, questionsOnly: false };
    }
    expandedExports.sets[setIdx].all = !expandedExports.sets[setIdx].all;
  }

  function toggleExportSetQuestionsOnly(setIdx) {
    if (!expandedExports.sets[setIdx]) {
      expandedExports.sets[setIdx] = { all: false, questionsOnly: false };
    }
    expandedExports.sets[setIdx].questionsOnly = !expandedExports.sets[setIdx].questionsOnly;
  }

  function downloadQuestionsOnlyAsText(setIndex) {
    const questions = questionSets[setIndex];
    let content = `# Questions Only - ${topic}\n\n`;
    questions.forEach((q, qIdx) => {
      content += `### Q${qIdx + 1}: ${q.description}\n\n`;
      q.options.forEach((opt, oIdx) => {
        content += `${String.fromCharCode(65 + oIdx)}. ${opt}\n`;
      });
      content += '\n';
    });
    const blob = new Blob([content], { type: 'text/plain' });
    downloadFile(blob, `${topic.replace(/\s+/g, '_')}_set_${setIndex + 1}_questions.txt`);
  }

  function downloadSetAsText(setId, setIndex) {
    const questions = questionSets[setIndex];
    let content = `# Set ${setIndex + 1} - ${topic}\n\n`;
    questions.forEach((q, qIdx) => {
      content += `### Q${qIdx + 1}: ${q.description}\n\n`;
      q.options.forEach((opt, oIdx) => {
        content += `${String.fromCharCode(65 + oIdx)}. ${opt}\n`;
      });
      content += `\n**Answer:** ${q.answer}\n`;
      if (q.explanation) {
        content += `**Explanation:** ${q.explanation}\n`;
      }
      content += '\n---\n\n';
    });
    const blob = new Blob([content], { type: 'text/plain' });
    downloadFile(blob, `${topic.replace(/\s+/g, '_')}_set_${setIndex + 1}.txt`);
  }
</script>

<div class="min-h-screen bg-gradient-to-br from-background via-background to-muted/20 py-4 md:py-6">
  <div class="max-w-7xl mx-auto px-3 sm:px-4">
    <!-- Header -->
    <div class="mb-6">
      <p class="text-muted-foreground">Create custom question sets instantly with AI</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">
      <!-- Form Sidebar -->
      <Card class="lg:sticky lg:top-4 lg:self-start order-2 lg:order-1" style="max-height: calc(100vh - 2rem); overflow-y: auto;">
        <CardHeader>
          <CardTitle>Generation Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <form onsubmit={generateQuestions} class="space-y-4">
            <!-- Topic -->
            <div class="space-y-2">
              <Label for="topic" class="text-sm font-semibold">Topic <span class="text-destructive">*</span></Label>
              <Input 
                id="topic" 
                bind:value={topic} 
                placeholder="e.g., Quantum Physics, Medieval History" 
                disabled={loading}
                class="text-base"
              />
            </div>

            <!-- Content -->
            <div class="space-y-2">
              <Label for="content" class="text-sm font-semibold">Content/Reference</Label>
              <Textarea 
                id="content" 
                bind:value={content} 
                placeholder="Optional: Paste text or context..." 
                disabled={loading}
                rows="3"
              />
            </div>

            <!-- File Upload -->
            <div class="space-y-2">
              <Label for="file" class="text-sm font-semibold">Upload File</Label>
              <Input 
                type="file" 
                id="file" 
                on:change={e => (files = e.target.files)} 
                accept=".pdf,.txt" 
                disabled={loading}
                class="cursor-pointer"
              />
              <p class="text-xs text-muted-foreground">PDF or TXT format</p>
            </div>

            <!-- Difficulty & Type Row -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="space-y-2">
                <Label for="difficulty" class="text-sm font-semibold">Difficulty</Label>
                <Select id="difficulty" bind:value={difficulty} disabled={loading}>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </Select>
              </div>
              <div class="space-y-2">
                <Label for="type" class="text-sm font-semibold">Type</Label>
                <Select id="type" bind:value={questionType} disabled={loading}>
                  <option value="multiple_choice">Multiple Choice</option>
                  <option value="true_false">True/False</option>
                  <option value="short_answer">Short Answer</option>
                </Select>
              </div>
            </div>

            <!-- Count & Sets Row -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="space-y-2">
                <Label for="numQ" class="text-sm font-semibold">Questions</Label>
                <Input 
                  type="number" 
                  id="numQ" 
                  bind:value={numQuestions} 
                  min="1" 
                  max="100"
                  disabled={loading}
                />
              </div>
              <div class="space-y-2">
                <Label for="numSets" class="text-sm font-semibold">Sets</Label>
                <Input 
                  type="number" 
                  id="numSets" 
                  bind:value={numSets} 
                  min="1" 
                  max="10"
                  disabled={loading}
                />
              </div>
            </div>

            <!-- Instructions -->
            <div class="space-y-2">
              <Label for="userContext" class="text-sm font-semibold">Custom Instructions</Label>
              <Textarea 
                id="userContext" 
                bind:value={userContext} 
                placeholder="e.g., Focus on practical examples..." 
                disabled={loading}
                rows="2"
              />
            </div>

            <!-- Web Search Toggle -->
            <div class="flex items-center space-x-2 p-3 bg-muted/50 rounded-lg border border-border">
              <input 
                type="checkbox" 
                id="webSearch" 
                bind:checked={useWebSearch}
                disabled={loading}
                class="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary focus:ring-2"
              />
              <Label for="webSearch" class="text-sm font-medium cursor-pointer flex items-center gap-2">
                <i class="fas fa-globe text-primary"></i>
                Enable Web Search (Ground with live data)
              </Label>
            </div>

            <!-- Generate Button -->
            <Button 
              type="submit" 
              class="w-full h-10 text-base font-semibold"
              disabled={loading || !topic.trim()}
            >
              {#if loading}
                <i class="fas fa-spinner fa-spin mr-2"></i>
                Generating...
              {:else}
                <i class="fas fa-plus mr-2"></i>
                Generate Questions
              {/if}
            </Button>

            <!-- Clear All Button -->
            {#if questionSets.length > 0 || topic.trim() || content.trim() || userContext.trim()}
              <Button 
                type="button"
                variant="outline"
                class="w-full h-10 text-sm sm:text-base font-semibold"
                onclick={clearAllData}
                disabled={loading}
              >
                <i class="fas fa-trash icon-left"></i>
                <span class="hidden sm:inline">Clear All Data</span><span class="sm:inline md:hidden">Clear All</span>
              </Button>
            {/if}

            <!-- Error Message -->
            {#if error}
              <div class="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
                <strong>Error:</strong> {error}
              </div>
            {/if}
          </form>
        </CardContent>
      </Card>

      <!-- Results Area -->
      <div class="lg:col-span-2 order-1 lg:order-2">
        {#if loading}
          <Card class="border-2 border-primary/20 bg-primary/5">
            <CardContent class="pt-12 pb-12">
              <div class="flex flex-col items-center justify-center text-center space-y-4">
                <div class="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
                <div>
                  <p class="font-semibold text-lg">{progressMessage}</p>
                  {#if currentStep}
                    <p class="text-sm text-muted-foreground mt-1 capitalize">{currentStep}</p>
                  {/if}
                  {#if totalSets > 0}
                    <div class="mt-3 w-48 h-2 bg-muted rounded-full overflow-hidden mx-auto">
                      <div 
                        class="h-full bg-primary transition-all duration-300"
                        style="width: {(completedSets / totalSets) * 100}%"
                      ></div>
                    </div>
                    <p class="text-xs text-muted-foreground mt-2">{completedSets} of {totalSets} sets completed</p>
                  {/if}
                  
                  {#if thinkingText}
                    <div class="mt-6 p-4 bg-slate-900/30 dark:bg-slate-100/5 rounded-lg border border-primary/20 max-w-2xl mx-auto backdrop-blur-md relative overflow-hidden">
                      <style>
                        @keyframes fadeIn {{
                          from {{ opacity: 0; }}
                          to {{ opacity: 0.6; }}
                        }}
                        .thinking-content {{
                          animation: fadeIn 0.6s ease-out;
                        }}
                        .thinking-box {{
                          background: linear-gradient(to bottom, 
                            rgba(15, 23, 42, 0.3) 0%,
                            rgba(15, 23, 42, 0.15) 10%,
                            rgba(15, 23, 42, 0.15) 90%,
                            rgba(15, 23, 42, 0.3) 100%
                          );
                          scroll-behavior: smooth;
                        }}
                        .thinking-box.dark {{
                          background: linear-gradient(to bottom, 
                            rgba(241, 245, 249, 0.08) 0%,
                            rgba(241, 245, 249, 0.04) 10%,
                            rgba(241, 245, 249, 0.04) 90%,
                            rgba(241, 245, 249, 0.08) 100%
                          );
                        }}
                      </style>
                      <p class="text-xs font-semibold text-primary mb-3 opacity-70">AI Thinking:</p>
                      <div 
                        bind:this={thinkingBoxEl}
                        class="thinking-box dark text-left text-xs text-foreground/60 font-mono whitespace-pre-wrap max-h-64 overflow-hidden break-words leading-relaxed thinking-content"
                      >
                        {thinkingText}
                      </div>
                    </div>
                  {/if}
                </div>
              </div>
            </CardContent>
          </Card>
        {:else if questionSets.length > 0}
          <div class="space-y-6">
            <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <h2 class="text-xl md:text-2xl font-bold">Your Generated Questions</h2>
              <div class="flex items-center gap-2 md:gap-3">
                <!-- {#if currentSetValidationThinking}
                  <Button 
                    variant="outline" 
                    onclick={() => showValidationModal = !showValidationModal}
                    class="flex items-center gap-2"
                  >
                    <i class="fas fa-brain"></i>
                    Validation Process
                  </Button>
                {/if} -->
                <Button 
                  variant="outline" 
                  onclick={toggleExportAll}
                  class="flex items-center gap-2 text-sm"
                >
                  <i class={`fas fa-chevron-down transition-transform ${expandedExports.all ? 'rotate-180' : ''}`}></i>
                  <span class="hidden sm:inline">Export </span>All
                </Button>
              </div>
            </div>
            {#if expandedExports.all}
              <div class="mt-3 p-2 sm:p-3 md:p-4 bg-muted rounded-lg border border-muted-foreground/20 flex flex-wrap gap-1.5 sm:gap-2">
                    <Button size="sm" variant="secondary" onclick={downloadAllAsJSON} class="shrink-0">
                      <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">JSON</span>
                    </Button>
                    <Button size="sm" variant="secondary" onclick={downloadAllAsCSV} class="shrink-0">
                      <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">CSV</span>
                    </Button>
                    <Button size="sm" variant="secondary" onclick={() => {
                      const doc = new jsPDF();
                      let yPosition = 10;
                      const pageHeight = doc.internal.pageSize.getHeight();
                      const pageWidth = doc.internal.pageSize.getWidth();
                      const margin = 10;
                      const maxWidth = pageWidth - (margin * 2);
                      
                      // Title
                      doc.setFontSize(18);
                      doc.setFont(undefined, 'bold');
                      doc.text(`Question Bank: ${topic}`, margin, yPosition);
                      yPosition += 8;
                      
                      doc.setFontSize(10);
                      doc.setFont(undefined, 'normal');
                      doc.text(`Difficulty: ${difficulty} | Type: ${questionType}`, margin, yPosition);
                      yPosition += 10;
                      
                      // Iterate through all sets
                      questionSets.forEach((set, setIdx) => {
                        // Set header
                        if (yPosition > pageHeight - 20) {
                          doc.addPage();
                          yPosition = 10;
                        }
                        
                        doc.setFontSize(14);
                        doc.setFont(undefined, 'bold');
                        doc.text(`Set ${setIdx + 1}`, margin, yPosition);
                        yPosition += 8;
                        
                        // Questions
                        doc.setFontSize(11);
                        set.forEach((q, qIdx) => {
                          // Check if we need a new page
                          if (yPosition > pageHeight - 40) {
                            doc.addPage();
                            yPosition = 10;
                          }
                          
                          // Question text
                          doc.setFont(undefined, 'bold');
                          const qLines = doc.splitTextToSize(`Q${qIdx + 1}: ${q.description}`, maxWidth);
                          doc.text(qLines, margin, yPosition);
                          yPosition += qLines.length * 5 + 3;
                          
                          // Options
                          doc.setFont(undefined, 'normal');
                          q.options.forEach((opt, oIdx) => {
                            if (yPosition > pageHeight - 15) {
                              doc.addPage();
                              yPosition = 10;
                            }
                            const optLines = doc.splitTextToSize(`  ${String.fromCharCode(65 + oIdx)}. ${opt}`, maxWidth - 5);
                            doc.text(optLines, margin + 5, yPosition);
                            yPosition += optLines.length * 5 + 1;
                          });
                          
                          // Answer and Explanation
                          if (yPosition > pageHeight - 20) {
                            doc.addPage();
                            yPosition = 10;
                          }
                          
                          doc.setFont(undefined, 'bold');
                          doc.text(`  Answer: ${q.answer}`, margin + 5, yPosition);
                          yPosition += 5;
                          
                          if (q.explanation) {
                            doc.setFont(undefined, 'italic');
                            const expLines = doc.splitTextToSize(`  Explanation: ${q.explanation}`, maxWidth - 5);
                            doc.text(expLines, margin + 5, yPosition);
                            yPosition += expLines.length * 5;
                          }
                          
                          yPosition += 5; // Space between questions
                        });
                        
                        yPosition += 5; // Extra space between sets
                      });
                      
                      doc.save(`${topic.replace(/\s+/g, '_')}_all_sets.pdf`);
                    }}>
                      <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">PDF</span>
                    </Button>
                    <Button size="sm" variant="secondary" onclick={downloadAllAsText} class="shrink-0">
                      <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">TXT</span>
                    </Button>
                  </div>
                {/if}

            {#if showValidationModal && currentSetValidationThinking}
              <!-- Modal Backdrop -->
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <!-- svelte-ignore a11y_click_events_have_key_events -->
              <div 
                class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                onclick={() => showValidationModal = false}
              >
                <!-- Modal Content -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <div 
                  class="bg-background rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] flex flex-col border-2 border-blue-500/30"
                  onclick={(e) => e.stopPropagation()}
                >
                  <!-- Header -->
                  <div class="bg-gradient-to-r from-blue-500 to-blue-600 dark:from-blue-600 dark:to-blue-700 px-6 py-5 rounded-t-2xl">
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-3">
                        <div class="p-2 bg-white/20 rounded-lg">
                          <i class="fas fa-brain text-white text-xl"></i>
                        </div>
                        <div>
                          <h2 class="text-xl font-bold text-white">LLM Validation Report</h2>
                          <p class="text-blue-100 text-sm">Detailed question analysis and quality checks</p>
                        </div>
                      </div>
                      <button 
                        onclick={() => showValidationModal = false}
                        class="p-2 hover:bg-white/20 rounded-lg transition-colors group"
                        title="Close"
                      >
                        <i class="fas fa-times text-white text-xl group-hover:rotate-90 transition-transform"></i>
                      </button>
                    </div>
                  </div>

                  <!-- Content -->
                  <div class="flex-1 overflow-y-auto p-6">
                    <div class="space-y-4">
                      <!-- Info Banner -->
                      <div class="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                        <div class="flex items-start gap-3">
                          <i class="fas fa-info-circle text-blue-600 dark:text-blue-400 mt-0.5"></i>
                          <div class="flex-1">
                            <p class="text-sm text-blue-900 dark:text-blue-100 font-medium mb-1">What is this report?</p>
                            <p class="text-xs text-blue-800 dark:text-blue-200">
                              This shows the LLM's detailed validation process where it checked each generated question for relevance, correctness, clarity, and quality. Any issues found are documented below.
                            </p>
                          </div>
                        </div>
                      </div>

                      <!-- Validation Content -->
                      <div class="bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
                        <div class="prose prose-sm dark:prose-invert max-w-none">
                          <div class="text-foreground/90 whitespace-pre-wrap break-words leading-relaxed font-mono text-sm">
                            {formatValidationText(currentSetValidationThinking)}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Footer -->
                  <div class="border-t border-border px-6 py-4 bg-muted/30 rounded-b-2xl">
                    <div class="flex items-center justify-between">
                      <p class="text-xs text-muted-foreground">
                        <i class="fas fa-shield-alt mr-1"></i>
                        Validation ensures question quality and accuracy
                      </p>
                      <div class="flex gap-2">
                        <Button 
                          size="sm" 
                          variant="outline"
                          onclick={() => {
                            const blob = new Blob([currentSetValidationThinking], { type: 'text/plain' });
                            downloadFile(blob, `validation_report_${Date.now()}.txt`);
                          }}
                          class="gap-2"
                        >
                          <i class="fas fa-download"></i>
                          Export Report
                        </Button>
                        <Button 
                          size="sm" 
                          onclick={() => showValidationModal = false}
                          class="gap-2"
                        >
                          <i class="fas fa-check"></i>
                          Close
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            {/if}

            {#each questionSets as questions, sIdx}
              <Card>
                <CardHeader class="cursor-pointer" onclick={() => collapsedSets[sIdx] = !collapsedSets[sIdx]}>
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <i class={`fas fa-chevron-right transition-transform ${!collapsedSets[sIdx] ? 'rotate-90' : ''}`}></i>
                      <CardTitle>Set # {sIdx + 1} <span class="text-sm text-muted-foreground font-normal">({questions.length} questions)</span></CardTitle>
                    </div>
                    <div class="flex items-center gap-2">
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onclick={(e) => {
                          e.stopPropagation();
                          toggleExportSetAll(sIdx);
                        }}
                        class="flex items-center gap-1"
                      >
                        <i class={`fas fa-chevron-down transition-transform text-xs ${expandedExports.sets[sIdx]?.all ? 'rotate-180' : ''}`}></i>
                        All
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onclick={(e) => {
                          e.stopPropagation();
                          toggleExportSetQuestionsOnly(sIdx);
                        }}
                        class="flex items-center gap-1"
                      >
                        <i class={`fas fa-chevron-down transition-transform text-xs ${expandedExports.sets[sIdx]?.questionsOnly ? 'rotate-180' : ''}`}></i>
                        Q only
                      </Button>
                    </div>
                  </div>
                  {#if expandedExports.sets[sIdx]?.all}
                    <div class="mt-3 p-2 sm:p-3 bg-muted rounded border border-muted-foreground/20 flex flex-wrap gap-1.5 sm:gap-2">
                      <Button size="sm" variant="secondary" onclick={() => exportSet(questions[0].set_id, 'json')} class="shrink-0">
                        <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">JSON</span>
                      </Button>
                      <Button size="sm" variant="secondary" onclick={() => exportSet(questions[0].set_id, 'csv')} class="shrink-0">
                        <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">CSV</span>
                      </Button>
                      <Button size="sm" variant="secondary" onclick={() => exportSet(questions[0].set_id, 'pdf')} class="shrink-0">
                        <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">PDF</span>
                      </Button>
                      <Button size="sm" variant="secondary" onclick={() => downloadSetAsText(questions[0].set_id, sIdx)} class="shrink-0">
                        <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">TXT</span>
                      </Button>
                    </div>
                  {/if}
                  {#if expandedExports.sets[sIdx]?.questionsOnly}
                    <div class="mt-3 p-2 sm:p-3 bg-muted rounded border border-muted-foreground/20 flex flex-wrap gap-1.5 sm:gap-2">
                      <Button size="sm" variant="secondary" onclick={() => {
                        const data = questions.map(q => ({ question: q.description, options: q.options }));
                        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                        downloadFile(blob, `${topic.replace(/\s+/g, '_')}_set_${sIdx + 1}_questions.json`);
                      }} class="shrink-0">
                        <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">JSON</span>
                      </Button>
                      <Button size="sm" variant="secondary" onclick={() => {
                        let csv = 'Question,Option A,Option B,Option C,Option D\n';
                        questions.forEach((q) => {
                          const options = q.options.slice(0, 4).concat(Array(4).fill('')).slice(0, 4);
                          csv += `"${q.description.replace(/"/g, '""')}","${options[0] ? options[0].replace(/"/g, '""') : ''}","${options[1] ? options[1].replace(/"/g, '""') : ''}","${options[2] ? options[2].replace(/"/g, '""') : ''}","${options[3] ? options[3].replace(/"/g, '""') : ''}"n`;
                        });
                        const blob = new Blob([csv], { type: 'text/csv' });
                        downloadFile(blob, `${topic.replace(/\s+/g, '_')}_set_${sIdx + 1}_questions.csv`);
                      }} class="shrink-0">
                        <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">CSV</span>
                      </Button>
                      <Button size="sm" variant="secondary" onclick={() => {
                        const doc = new jsPDF();
                        let yPosition = 10;
                        const pageHeight = doc.internal.pageSize.getHeight();
                        const lineHeight = 7;
                        
                        doc.setFontSize(16);
                        doc.text(`QUESTIONS ONLY - ${topic}`, 10, yPosition);
                        yPosition += 10;
                        
                        doc.setFontSize(11);
                        questions.forEach((q, idx) => {
                          if (yPosition > pageHeight - 20) {
                            doc.addPage();
                            yPosition = 10;
                          }
                          
                          doc.setFont(undefined, 'bold');
                          doc.text(`Q${idx + 1}: ${q.description}`, 10, yPosition, { maxWidth: 190 });
                          yPosition += doc.getTextDimensions(q.description, { maxWidth: 190 }).h + 5;
                          
                          doc.setFont(undefined, 'normal');
                          q.options.forEach((opt, oIdx) => {
                            if (yPosition > pageHeight - 15) {
                              doc.addPage();
                              yPosition = 10;
                            }
                            doc.text(`${String.fromCharCode(65 + oIdx)}. ${opt}`, 15, yPosition, { maxWidth: 185 });
                            yPosition += doc.getTextDimensions(opt, { maxWidth: 185 }).h + 3;
                          });
                          yPosition += 3;
                        });
                        
                        doc.save(`${topic.replace(/\s+/g, '_')}_set_${sIdx + 1}_questions.pdf`);
                      }} class="shrink-0">
                        <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">PDF</span>
                      </Button>
                      <Button size="sm" variant="secondary" onclick={() => downloadQuestionsOnlyAsText(sIdx)} class="shrink-0">
                        <i class="fas fa-download"></i><span class="hidden sm:inline ml-1">TXT</span>
                      </Button>
                    </div>
                  {/if}
                </CardHeader>
                {#if !collapsedSets[sIdx]}
                <CardContent>
                  <div class="space-y-4">{#each questions as q, qIdx}
                      <div 
                        class="border rounded-lg p-4 hover:bg-muted/50 transition-colors relative cursor-pointer" 
                        onclick={() => {
                          const key = `${sIdx}_${qIdx}`;
                          collapsedQuestions[key] = !collapsedQuestions[key];
                        }}
                        role="button"
                        tabindex="0"
                        onkeydown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            const key = `${sIdx}_${qIdx}`;
                            collapsedQuestions[key] = !collapsedQuestions[key];
                          }
                        }}
                      >
                        {#if regeneratingQuestionId === q.id}
                          <div class="absolute inset-0 bg-background/80 backdrop-blur-sm rounded-lg flex items-center justify-center z-10">
                            <div class="flex flex-col items-center gap-2">
                              <div class="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
                              <p class="text-sm text-muted-foreground">Regenerating...</p>
                            </div>
                          </div>
                        {/if}
                        <div class="flex gap-3 items-start mb-3">
                          <div class="flex items-center gap-2">
                            <i class={`fas fa-chevron-right transition-transform text-xs ${!collapsedQuestions[`${sIdx}_${qIdx}`] ? 'rotate-90' : ''}`}></i>
                            <span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary text-sm font-bold flex-shrink-0">
                              {qIdx + 1}
                            </span>
                          </div>
                          <p class="font-medium flex-1 text-base leading-relaxed">{q.description}</p>
                          <button 
                            class="p-1.5 rounded hover:bg-muted transition-all text-muted-foreground hover:text-primary flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed" 
                            onclick={(e) => {
                              e.stopPropagation();
                              regenerateQuestion(q.id, sIdx, qIdx);
                            }}
                            disabled={regeneratingQuestionId === q.id}
                            title="Regenerate this question"
                          >
                            <i class="fas fa-redo"></i>
                          </button>
                        </div>
                        {#if !collapsedQuestions[`${sIdx}_${qIdx}`]}
                        <div class="space-y-2 ml-9">
                          {#each q.options as opt, oIdx}
                            <div 
                              class="p-2.5 rounded border transition-colors {
                                opt === q.answer 
                                  ? 'bg-green-100 border-green-400 dark:bg-green-900/60 dark:border-green-500' 
                                  : 'bg-muted/50 border-transparent hover:border-muted-foreground/20'
                              }"
                            >
                              <div class="flex items-start gap-2">
                                <span class="text-xs font-bold text-muted-foreground w-4">{String.fromCharCode(65 + oIdx)}.</span>
                                <span class={`text-sm flex-1 ${opt === q.answer ? 'font-medium text-green-800 dark:text-green-200' : ''}`}>{opt}</span>
                                {#if opt === q.answer}
                                  <span class="text-xs font-bold text-green-800 dark:text-green-200 flex-shrink-0">✓</span>
                                {/if}
                              </div>
                            </div>
                          {/each}
                        </div>
                        {#if q.explanation}
                          <div class="mt-3 ml-9 p-2.5 bg-blue-100 dark:bg-blue-900/60 rounded border border-blue-300 dark:border-blue-500">
                            <p class="text-xs font-semibold text-blue-800 dark:text-blue-200 mb-1">Explanation:</p>
                            <p class="text-sm text-blue-800 dark:text-blue-200">{q.explanation}</p>
                          </div>
                        {/if}
                        {/if}
                      </div>
                    {/each}
                  </div>
                </CardContent>
                {/if}
              </Card>
            {/each}
          </div>
        {:else}
          <Card class="border-2 border-dashed border-muted-foreground/20">
            <CardContent class="pt-12 pb-12">
              <div class="flex flex-col items-center justify-center text-center space-y-4">
                <div class="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
                  <i class="fas fa-plus text-muted-foreground" style="font-size: 24px;"></i>
                </div>
                <div>
                  <p class="font-semibold text-lg">No questions yet</p>
                  <p class="text-sm text-muted-foreground mt-1">Enter a topic and click "Generate Questions" to get started</p>
                </div>
              </div>
            </CardContent>
          </Card>
        {/if}
      </div>
    </div>
  </div>
</div>