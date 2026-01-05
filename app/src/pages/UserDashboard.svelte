<script>
  import { authState } from "../stores/auth";
  import { onMount } from "svelte";
  import { navigate } from "../stores/router";
  import { API_URL } from "../config/api";
  import { Button } from "$lib/components/ui/button";
  import { Card, CardContent, CardHeader, CardTitle } from "$lib/components/ui/card";

  let token;
  let user;
  authState.subscribe(v => {
    token = v.token;
    user = v.user;
  });

  // Dashboard stats
  let stats = {
    total_generations: 0,
    total_questions: 0,
    pending_tasks: 0,
    completed_tasks: 0
  };

  // Data
  let recentGenerations = [];
  let myTasks = [];
  let loading = true;

  onMount(() => {
    if (!token) {
      navigate("/login");
      return;
    }
    fetchDashboard();
    
    // Listen for stats update events
    const handleStatsUpdate = () => fetchStats();
    window.addEventListener('statsUpdate', handleStatsUpdate);
    
    return () => {
      window.removeEventListener('statsUpdate', handleStatsUpdate);
    };
  });

  async function fetchDashboard() {
    loading = true;
    await Promise.all([
      fetchStats(),
      fetchRecentGenerations(),
      fetchMyTasks()
    ]);
    loading = false;
  }

  async function fetchStats() {
    try {
      const res = await fetch(`${API_URL}/user/dashboard`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) stats = await res.json();
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    }
  }

  async function fetchRecentGenerations() {
    try {
      const res = await fetch(`${API_URL}/history`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const all = await res.json();
        recentGenerations = all.slice(0, 5);
      }
    } catch (e) {
      console.error("Failed to fetch generations:", e);
    }
  }

  async function fetchMyTasks() {
    try {
      const res = await fetch(`${API_URL}/tasks/my`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) myTasks = await res.json();
    } catch (e) {
      console.error("Failed to fetch tasks:", e);
    }
  }

  function formatDate(date) {
    return new Date(date).toLocaleString();
  }

  function getStatusColor(status) {
    const colors = {
      pending: "bg-yellow-500",
      in_progress: "bg-blue-500",
      completed: "bg-green-500",
      cancelled: "bg-gray-500"
    };
    return colors[status] || "bg-gray-500";
  }

  function startTask(task) {
    // Navigate to generation page with task data pre-filled
    navigate("/generate", {
      state: {
        taskId: task.id,
        topic: task.topic,
        numQuestions: task.num_questions,
        numSets: task.num_sets,
        difficulty: task.difficulty,
        questionType: task.question_type,
        userContext: task.user_context || ""
      }
    });
  }
</script>

<div class="container mx-auto p-4 md:p-6 max-w-6xl">
  <div class="mb-6">
    <h1 class="text-3xl font-bold">Welcome back!</h1>
    <p class="text-muted-foreground">Here's your activity overview</p>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-20">
      <i class="fas fa-spinner fa-spin text-4xl text-primary"></i>
    </div>
  {:else}
    <!-- Stats Cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6">
      <Card>
        <CardContent class="pt-6">
          <div class="text-2xl font-bold">{stats.total_generations}</div>
          <p class="text-sm text-muted-foreground">Total Generations</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-6">
          <div class="text-2xl font-bold">{stats.total_questions}</div>
          <p class="text-sm text-muted-foreground">Questions Created</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-6">
          <div class="text-2xl font-bold text-yellow-500">{stats.pending_tasks}</div>
          <p class="text-sm text-muted-foreground">Pending Tasks</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-6">
          <div class="text-2xl font-bold text-green-500">{stats.completed_tasks}</div>
          <p class="text-sm text-muted-foreground">Completed Tasks</p>
        </CardContent>
      </Card>
    </div>

    <!-- Quick Actions -->
    <div class="mb-6">
      <Button class="w-full md:w-auto" onclick={() => navigate("/generate")}>
        <i class="fas fa-plus mr-2"></i>New Generation
      </Button>
    </div>

    <div class="grid grid-cols-1 gap-6">
      <!-- Assigned Tasks -->
      <Card>
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <i class="fas fa-tasks"></i>
            Assigned Tasks
            {#if myTasks.filter(t => t.status === 'pending').length > 0}
              <span class="bg-yellow-500 text-white text-xs px-2 py-0.5 rounded-full">
                {myTasks.filter(t => t.status === 'pending').length} pending
              </span>
            {/if}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="space-y-3 max-h-96 overflow-y-auto">
            {#each myTasks as task}
              <div class="p-4 bg-muted rounded-lg">
                <div class="flex justify-between items-start mb-2">
                  <div>
                    <h3 class="font-semibold">{task.title}</h3>
                    <p class="text-sm text-muted-foreground">{task.description || 'No description'}</p>
                  </div>
                  <span class={`px-2 py-1 text-xs rounded-full text-white ${getStatusColor(task.status)}`}>
                    {task.status}
                  </span>
                </div>
                <div class="text-sm text-muted-foreground mb-3">
                  <span class="mr-3"><i class="fas fa-book mr-1"></i>{task.topic}</span>
                  <span class="mr-3"><i class="fas fa-question-circle mr-1"></i>{task.num_questions} × {task.num_sets}</span>
                  <span><i class="fas fa-tachometer-alt mr-1"></i>{task.difficulty}</span>
                </div>
                {#if task.status === "pending"}
                  <Button size="sm" onclick={() => startTask(task)}>
                    <i class="fas fa-play mr-1"></i>Start Task
                  </Button>
                {:else if task.status === "completed"}
                  <span class="text-sm text-green-500">
                    <i class="fas fa-check-circle mr-1"></i>Completed {task.completed_at ? formatDate(task.completed_at) : ''}
                  </span>
                {/if}
              </div>
            {:else}
              <p class="text-muted-foreground text-center py-4">No tasks assigned yet</p>
            {/each}
          </div>
        </CardContent>
      </Card>

      <!-- Recent Generations -->
      <Card>
        <CardHeader class="flex flex-row items-center justify-between">
          <CardTitle class="flex items-center gap-2">
            <i class="fas fa-history"></i>
            Recent Generations
          </CardTitle>
          <Button variant="outline" size="sm" onclick={() => navigate("/history")}>
            View All
          </Button>
        </CardHeader>
        <CardContent>
          <div class="space-y-3 max-h-96 overflow-y-auto">
            {#each recentGenerations as gen}
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <!-- svelte-ignore a11y_click_events_have_key_events -->
              <div class="p-3 bg-muted rounded-lg flex justify-between items-center hover:bg-muted/80 cursor-pointer"
                   onclick={() => navigate("/history")}>
                <div>
                  <p class="font-medium">{gen.topic}</p>
                  <p class="text-sm text-muted-foreground">
                    {gen.question_count || gen.questions?.length || 0} questions • {gen.difficulty}
                  </p>
                </div>
                <span class="text-xs text-muted-foreground">{formatDate(gen.created_at)}</span>
              </div>
            {:else}
              <div class="text-center py-8">
                <i class="fas fa-inbox text-4xl text-muted-foreground mb-2"></i>
                <p class="text-muted-foreground">No generations yet</p>
                <Button class="mt-2" onclick={() => navigate("/generate")}>
                  Create Your First
                </Button>
              </div>
            {/each}
          </div>
        </CardContent>
      </Card>
    </div>
  {/if}
</div>
