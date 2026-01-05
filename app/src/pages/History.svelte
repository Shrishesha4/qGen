<script>
  import { authState } from "../stores/auth";
  import { onMount } from "svelte";
  import { navigate } from "../stores/router";
  import { jsPDF } from "jspdf";
  import { API_URL } from "../config/api";
  import { Button } from "$lib/components/ui/button";
  import { Card, CardHeader, CardTitle, CardContent } from "$lib/components/ui/card";

  let token;
  authState.subscribe(v => token = v.token);

  let historyGroups = [];
  let loading = true;
  let currentView = "groups"; // "groups", "sets", "questions", "question_detail"
  let selectedGroup = null;
  let selectedSet = null;
  let selectedQuestion = null;
  
  // Export state
  let expandedExports = {
    all: false,
    questionsOnly: false
  };
  
  // Regeneration loading state
  let regeneratingQuestionId = null;
  let regeneratingSetId = null;

  // Validation modal state
  let showValidationModal = false;
  let validationText = "";

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

  async function fetchHistory() {
    try {
      const res = await fetch(`${API_URL}/history`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const sets = await res.json();
        historyGroups = groupSets(sets);
      }
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  }

  function groupSets(sets) {
    const groups = {};
    
    sets.forEach(set => {
      const date = new Date(set.created_at);
      const timeKey = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()} ${date.getHours()}:${date.getMinutes()}`;
      const key = `${set.topic}::${timeKey}`;
      
      if (!groups[key]) {
        groups[key] = {
          id: key,
          topic: set.topic,
          date: date,
          sets: []
        };
      }
      groups[key].sets.push(set);
    });

    return Object.values(groups).sort((a, b) => b.date - a.date);
  }

  function selectGroup(group) {
    selectedGroup = group;
    currentView = "sets";
  }

  function selectSet(set) {
    selectedSet = set;
    currentView = "questions";
  }

  function selectQuestion(question) {
    selectedQuestion = question;
    currentView = "question_detail";
  }

  function goBack() {
    if (currentView === "question_detail") {
      currentView = "questions";
      selectedQuestion = null;
    } else if (currentView === "questions") {
      currentView = "sets";
      selectedSet = null;
    } else if (currentView === "sets") {
      currentView = "groups";
      selectedGroup = null;
    }
  }

  async function regenerateSet(set) {
    navigate("/dashboard", { state: { regenerationData: set } });
  }

  async function regenerateQuestion(questionId) {
    try {
      if (!questionId) {
        console.error("Question ID is missing:", { selectedQuestion, questionId });
        throw new Error("Question ID is missing");
      }
      regeneratingQuestionId = questionId;
      loading = true;
      const res = await fetch(`${API_URL}/regenerate/${questionId}`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Error: ${res.status}`);
      }
      const newQuestion = await res.json();
      
      const qIdx = selectedSet.questions.findIndex(q => q.id === questionId);
      selectedSet.questions[qIdx] = newQuestion;
      selectedQuestion = newQuestion;
      selectedSet = selectedSet;
    } catch (e) { 
      alert(e.message); 
    } finally {
      regeneratingQuestionId = null;
      loading = false;
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

  function downloadFile(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
  }

  function downloadSetAsJson() {
    const data = {
      topic: selectedSet.topic,
      difficulty: selectedSet.difficulty,
      questions: selectedSet.questions
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    downloadFile(blob, `set_${selectedSet.id}.json`);
  }

  function downloadSetAsCsv() {
    let csv = 'Question Number,Question,Option A,Option B,Option C,Option D,Correct Answer,Explanation\n';
    selectedSet.questions.forEach((q, idx) => {
      const options = q.options.slice(0, 4).concat(Array(4).fill('')).slice(0, 4);
      csv += `${idx + 1},"${q.description.replace(/"/g, '""')}","${options[0] ? options[0].replace(/"/g, '""') : ''}","${options[1] ? options[1].replace(/"/g, '""') : ''}","${options[2] ? options[2].replace(/"/g, '""') : ''}","${options[3] ? options[3].replace(/"/g, '""') : ''}","${q.answer.replace(/"/g, '""')}","${(q.explanation || '').replace(/"/g, '""')}"\n`;
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    downloadFile(blob, `set_${selectedSet.id}.csv`);
  }

  function downloadSetAsPdf() {
    const data = selectedSet.questions.map((q, idx) => ({
      number: idx + 1,
      description: q.description,
      options: q.options,
      answer: q.answer,
      explanation: q.explanation
    }));
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/pdf' });
    downloadFile(blob, `set_${selectedSet.id}.pdf`);
  }

  function downloadSetAsText() {
    let content = `# ${selectedSet.topic} - Set ${selectedSet.id}\n\n`;
    selectedSet.questions.forEach((q, idx) => {
      content += `### Q${idx + 1}: ${q.description}\n\n`;
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
    downloadFile(blob, `set_${selectedSet.id}.txt`);
  }

  function downloadQuestionsOnlyAsJson() {
    const data = selectedSet.questions.map(q => ({
      question: q.description,
      options: q.options
    }));
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    downloadFile(blob, `set_${selectedSet.id}_questions_only.json`);
  }

  function downloadQuestionsOnlyAsCsv() {
    let csv = 'Question Number,Question,Option A,Option B,Option C,Option D\n';
    selectedSet.questions.forEach((q, idx) => {
      const options = q.options.slice(0, 4).concat(Array(4).fill('')).slice(0, 4);
      csv += `${idx + 1},"${q.description.replace(/"/g, '""')}","${options[0] ? options[0].replace(/"/g, '""') : ''}","${options[1] ? options[1].replace(/"/g, '""') : ''}","${options[2] ? options[2].replace(/"/g, '""') : ''}","${options[3] ? options[3].replace(/"/g, '""') : ''}"\n`;
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    downloadFile(blob, `set_${selectedSet.id}_questions_only.csv`);
  }

  function downloadQuestionsOnlyAsPdf() {
    const doc = new jsPDF();
    let yPosition = 10;
    const pageHeight = doc.internal.pageSize.getHeight();
    const lineHeight = 7;
    
    doc.setFontSize(16);
    doc.text(`${selectedSet.topic}`, 10, yPosition);
    yPosition += 10;
    
    doc.setFontSize(11);
    selectedSet.questions.forEach((q, idx) => {
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
    
    doc.save(`set_${selectedSet.id}_questions_only.pdf`);
  }

  function downloadQuestionsOnlyAsText() {
    let content = `# ${selectedSet.topic}\n\n`;
    selectedSet.questions.forEach((q, idx) => {
      content += `### Q${idx + 1}: ${q.description}\n\n`;
      q.options.forEach((opt, oIdx) => {
        content += `${String.fromCharCode(65 + oIdx)}. ${opt}\n`;
      });
      content += '\n';
    });
    const blob = new Blob([content], { type: 'text/plain' });
    downloadFile(blob, `set_${selectedSet.id}_questions_only.txt`);
  }

  async function deleteSet(setId) {
    if (!confirm("Are you sure you want to delete this question set?")) return;
    
    try {
      loading = true;
      const res = await fetch(`${API_URL}/history/${setId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Delete failed");
      
      // Remove from local state
      historyGroups = historyGroups.map(group => ({
        ...group,
        sets: group.sets.filter(set => set.id !== setId)
      })).filter(group => group.sets.length > 0);
      
      // Trigger stats refresh by dispatching event
      window.dispatchEvent(new CustomEvent('statsUpdate'));
      
      goBack();
    } catch (e) { 
      alert(e.message); 
    } finally {
      loading = false;
    }
  }

  async function deleteAllSetsInGroup(group) {
    if (!confirm(`Are you sure you want to delete all ${group.sets.length} set(s) from "${group.topic}"?`)) return;
    
    try {
      loading = true;
      await Promise.all(
        group.sets.map(set => 
          fetch(`${API_URL}/history/${set.id}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
          })
        )
      );
      
      historyGroups = historyGroups.filter(g => g.id !== group.id);
      
      // Trigger stats refresh by dispatching event
      window.dispatchEvent(new CustomEvent('statsUpdate'));
      
      goBack();
    } catch (e) { 
      alert(e.message); 
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!token) navigate("/login");
    else fetchHistory();
  });
</script>

<div class="min-h-screen bg-gradient-to-br from-background via-background to-muted/20 py-8">
  <div class="max-w-4xl mx-auto px-4">
    <!-- Header with Navigation -->
    <div class="mb-8">
      <div class="flex items-center gap-2 mb-4">
        {#if currentView !== "groups"}
          <Button variant="ghost" size="sm" onclick={goBack} class="gap-2">
            <i class="fas fa-arrow-left"></i>
            Back
          </Button>
        {/if}
      </div>
      
      <h1 class="text-4xl font-bold tracking-tight mb-2">
        <!-- svelte-ignore block_empty -->
        {#if currentView === "sets"}
          {selectedGroup.topic}
        {:else if currentView === "questions"}
          Set #{selectedSet.id}
        {:else}
          Question Details
        {/if}
      </h1>
      
      {#if currentView === "groups"}
        <p class="text-muted-foreground">Browse your generated question sets</p>
      {:else if currentView === "sets"}
        <p class="text-muted-foreground text-sm">{new Date(selectedGroup.date).toLocaleString()}</p>
      {:else if currentView === "questions"}
        <p class="text-muted-foreground text-sm">{selectedSet.questions.length} questions • {selectedSet.difficulty}</p>
      {/if}
    </div>
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
    {#if loading && currentView === "groups"}
      <div class="flex items-center justify-center h-64 text-muted-foreground">Loading history...</div>
    {:else if historyGroups.length === 0 && currentView === "groups"}
      <Card>
        <CardContent class="pt-12 pb-12">
          <div class="flex flex-col items-center justify-center text-center space-y-4">
            <div class="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
              <i class="fas fa-file text-muted-foreground" style="font-size: 24px;"></i>
            </div>
            <div>
              <p class="font-semibold text-lg">No history yet</p>
              <p class="text-sm text-muted-foreground mt-1">Generate question sets to see them here</p>
            </div>
          </div>
        </CardContent>
      </Card>

    <!-- Groups View -->
    {:else if currentView === "groups"}
      <div class="space-y-3">
        {#each historyGroups as group}
          <Card 
            class="hover:bg-accent transition-colors" 
          >

            <CardContent class="pt-6 pb-6">
              <div class="flex items-center justify-between">
                <div 
                  class="flex items-center gap-3 flex-1 cursor-pointer"
                  onclick={() => selectGroup(group)}
                >
                  <div class="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <i class="fas fa-folder text-primary"></i>
                  </div>
                  <div>
                    <p class="font-semibold text-lg">{group.topic}</p>
                    <p class="text-sm text-muted-foreground">{group.sets.length} set{group.sets.length !== 1 ? 's' : ''} • {new Date(group.date).toLocaleString()}</p>
                  </div>
                </div>
                <div class="flex items-center gap-2 flex-shrink-0 ml-4">
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onclick={(e) => { e.stopPropagation(); selectGroup(group); }}
                    class="text-muted-foreground hover:text-primary"
                  >
                    <i class="fas fa-chevron-right"></i>
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onclick={(e) => { e.stopPropagation(); deleteAllSetsInGroup(group); }}
                    disabled={loading}
                    class="text-destructive hover:text-destructive/80 hover:bg-destructive/10"
                  >
                    <i class="fas fa-trash"></i>
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        {/each}
      </div>

    <!-- Sets View -->
    {:else if currentView === "sets" && selectedGroup}
      <div class="space-y-3">
        {#each selectedGroup.sets as set, idx}
          <Card 
            class="hover:bg-accent transition-colors"
          >
            <CardContent class="pt-6 pb-6">
              <div class="flex items-center justify-between">
                <div 
                  class="flex items-center gap-3 flex-1 cursor-pointer"
                  onclick={() => selectSet(set)}
                >
                  <div class="h-10 w-10 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                    <i class="fas fa-file-alt text-blue-600"></i>
                  </div>
                  <div>
                    <p class="font-semibold text-lg">Set #{idx + 1}</p>
                    <p class="text-sm text-muted-foreground">{set.questions.length} questions • {set.difficulty} • {set.question_type}</p>
                  </div>
                </div>
                <div class="flex items-center gap-2 flex-shrink-0 ml-4">
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onclick={(e) => { e.stopPropagation(); selectSet(set); }}
                    class="text-muted-foreground hover:text-primary"
                  >
                    <i class="fas fa-chevron-right"></i>
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onclick={(e) => { e.stopPropagation(); deleteSet(set.id); }}
                    disabled={loading}
                    class="text-destructive hover:text-destructive/80 hover:bg-destructive/10"
                  >
                    <i class="fas fa-trash"></i>
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        {/each}
      </div>

    <!-- Questions View -->
    {:else if currentView === "questions" && selectedSet}
      <div class="space-y-3 mb-6">
        {#each selectedSet.questions as question, idx}
          <Card 
            class="cursor-pointer hover:bg-accent transition-colors relative"
            onclick={() => selectQuestion(question)}
          >
            {#if regeneratingQuestionId === question.id}
              <div class="absolute inset-0 bg-background/80 backdrop-blur-sm rounded-lg flex items-center justify-center z-10">
                <div class="flex flex-col items-center gap-2">
                  <div class="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
                  <p class="text-sm text-muted-foreground">Regenerating...</p>
                </div>
              </div>
            {/if}
            <CardContent class="pt-6 pb-6">
              <div class="flex items-start justify-between gap-4">
                <div class="flex items-start gap-3 flex-1">
                  <div class="h-8 w-8 rounded-full bg-green-500/10 flex items-center justify-center flex-shrink-0 text-sm font-bold text-green-600 mt-0.5">
                    {idx + 1}
                  </div>
                  <div class="flex-1">
                    <p class="font-medium text-base line-clamp-2">{question.description}</p>
                  </div>
                </div>
                <i class="fas fa-chevron-right text-muted-foreground flex-shrink-0"></i>
              </div>
            </CardContent>
          </Card>
        {/each}
      </div>

      <!-- Set Actions -->
      <Card class="bg-muted/30 border-dashed relative">
        {#if regeneratingSetId === selectedSet.id}
          <div class="absolute inset-0 bg-background/80 backdrop-blur-sm rounded-lg flex items-center justify-center z-10">
            <div class="flex flex-col items-center gap-2">
              <div class="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
              <p class="text-sm text-muted-foreground">Regenerating set...</p>
            </div>
          </div>
        {/if}
        <CardContent class="pt-6 pb-6">
          <div class="flex flex-col gap-3">
            <!-- {#if selectedSet.validation_text}
              <Button 
                variant="outline"
                onclick={() => {
                  showValidationModal = true;
                  validationText = selectedSet.validation_text;
                }}
                class="w-full justify-center gap-2"
              >
                <i class="fas fa-brain"></i>
                Validation Process
              </Button>
            {/if} -->
            <Button 
              onclick={() => {
                regeneratingSetId = selectedSet.id;
                regenerateSet(selectedSet);
              }}
              disabled={loading || regeneratingSetId === selectedSet.id}
              class="w-full justify-center gap-2"
            >
              <i class="fas fa-redo"></i>
              Regenerate Entire Set
            </Button>
            <div class="flex gap-2">
              <Button 
                variant="outline"
                size="sm"
                onclick={() => expandedExports.all = !expandedExports.all}
                class="flex-1 flex items-center justify-center gap-1"
              >
                <i class={`fas fa-chevron-down transition-transform ${expandedExports.all ? 'rotate-180' : ''}`}></i>
                All
              </Button>
              <Button 
                variant="outline"
                size="sm"
                onclick={() => expandedExports.questionsOnly = !expandedExports.questionsOnly}
                class="flex-1 flex items-center justify-center gap-1"
              >
                <i class={`fas fa-chevron-down transition-transform ${expandedExports.questionsOnly ? 'rotate-180' : ''}`}></i>
                Q only
              </Button>
            </div>
            {#if expandedExports.all}
              <div class="p-3 bg-background rounded border border-muted-foreground/20 flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" onclick={downloadSetAsJson}>
                  <i class="fas fa-download mr-1"></i>JSON
                </Button>
                <Button size="sm" variant="secondary" onclick={downloadSetAsCsv}>
                  <i class="fas fa-download mr-1"></i>CSV
                </Button>
                <Button size="sm" variant="secondary" onclick={downloadSetAsPdf}>
                  <i class="fas fa-download mr-1"></i>PDF
                </Button>
                <Button size="sm" variant="secondary" onclick={downloadSetAsText}>
                  <i class="fas fa-download mr-1"></i>TXT
                </Button>
              </div>
            {/if}
            {#if expandedExports.questionsOnly}
              <div class="p-3 bg-background rounded border border-muted-foreground/20 flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" onclick={downloadQuestionsOnlyAsJson}>
                  <i class="fas fa-download mr-1"></i>JSON
                </Button>
                <Button size="sm" variant="secondary" onclick={downloadQuestionsOnlyAsCsv}>
                  <i class="fas fa-download mr-1"></i>CSV
                </Button>
                <Button size="sm" variant="secondary" onclick={downloadQuestionsOnlyAsPdf}>
                  <i class="fas fa-download mr-1"></i>PDF
                </Button>
                <Button size="sm" variant="secondary" onclick={downloadQuestionsOnlyAsText}>
                  <i class="fas fa-download mr-1"></i>TXT
                </Button>
              </div>
            {/if}
          </div>
        </CardContent>
      </Card>

    <!-- Question Detail View -->
    {:else if currentView === "question_detail" && selectedQuestion}
      <Card class="border-2 border-primary/20">
        <CardContent class="pt-8 pb-8">
          <div class="space-y-6">
            <!-- Question Text -->
            <div>
              <p class="text-lg font-semibold mb-4">{selectedQuestion.description}</p>
            </div>

            <!-- Options -->
            <div class="space-y-3">
              <p class="text-sm font-semibold text-muted-foreground uppercase">Options:</p>
              {#each selectedQuestion.options as option, idx}
                <div 
                  class="p-4 rounded-lg border-2 transition-colors {
                    option === selectedQuestion.answer 
                      ? 'border-green-400 bg-green-100 dark:bg-green-900/60' 
                      : 'border-muted hover:border-muted-foreground/30'
                  }"
                >
                  <div class="flex items-start gap-3">
                    <span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-muted text-sm font-bold flex-shrink-0">
                      {String.fromCharCode(65 + idx)}
                    </span>
                    <span class={`text-base flex-1 ${option === selectedQuestion.answer ? 'font-semibold text-green-800 dark:text-green-200' : ''}`}>
                      {option}
                    </span>
                    {#if option === selectedQuestion.answer}
                      <span class="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 text-xs font-bold flex-shrink-0">
                        <i class="fas fa-check"></i>
                        Correct
                      </span>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>

            <!-- Explanation -->
            {#if selectedQuestion.explanation}
              <div class="p-4 bg-blue-100 dark:bg-blue-900/60 rounded-lg border border-blue-300 dark:border-blue-500">
                <p class="text-sm font-semibold text-blue-800 dark:text-blue-200 mb-2">Explanation:</p>
                <p class="text-base text-blue-800 dark:text-blue-200">{selectedQuestion.explanation}</p>
              </div>
            {/if}

            <!-- Question Actions -->
            <div class="flex gap-2 pt-4 border-t">
              <Button 
                onclick={() => regenerateQuestion(selectedQuestion.id)}
                disabled={loading}
                class="gap-2"
              >
                  <i class="fas fa-redo"></i>
                Regenerate Question
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    {/if}

    <!-- Validation Modal -->
    {#if showValidationModal && validationText}
      <!-- Modal Backdrop -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <div 
        class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onclick={() => showValidationModal = false}
      >
        <!-- Modal Content -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
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
                    {formatValidationText(validationText)}
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
                    const blob = new Blob([validationText], { type: 'text/plain' });
                    downloadFile(blob, `validation_report_set_${selectedSet.id}.txt`);
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
  </div>
</div>