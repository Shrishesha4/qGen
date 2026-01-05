<script>
  import { authState } from "../stores/auth";
  import { onMount, onDestroy } from "svelte";
  import { navigate } from "../stores/router";
  import { API_URL } from "../config/api";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Label } from "$lib/components/ui/label";
  import { Textarea } from "$lib/components/ui/textarea";
  import { Select } from "$lib/components/ui/select";
  import { Card, CardContent, CardHeader, CardTitle } from "$lib/components/ui/card";

  let token;
  let user;
  authState.subscribe(v => {
    token = v.token;
    user = v.user;
  });

  // Dashboard stats
  let stats = {
    total_users: 0,
    active_users: 0,
    total_generations: 0,
    total_questions: 0,
    active_sessions: 0,
    pending_tasks: 0
  };

  // Data
  let users = [];
  let recentGenerations = [];
  let activeSessions = [];
  let tasks = [];
  let allHistory = [];
  let selectedHistorySet = null;
  let showHistoryDetailModal = false;

  // UI State
  let loading = true;
  let activeTab = "overview";
  let showCreateTaskModal = false;
  let showCreateUserModal = false;
  let refreshInterval;
  let ws; // WebSocket connection

  // Create task form
  let newTask = {
    title: "",
    description: "",
    topic: "",
    num_questions: 5,
    num_sets: 1,
    difficulty: "medium",
    question_type: "multiple_choice",
    user_context: "",
    assignee_id: null,
    due_date: ""
  };

  // Create user form
  let newUser = {
    email: "",
    password: ""
  };

  let createError = "";

  onMount(() => {
    if (!token) {
      navigate("/login");
      return;
    }
    fetchDashboard();
    
    // Connect to WebSocket for real-time session updates
    connectWebSocket();
    
    // Listen for stats update events from other components
    const handleStatsUpdate = () => fetchStats();
    window.addEventListener('statsUpdate', handleStatsUpdate);
    
    return () => {
      window.removeEventListener('statsUpdate', handleStatsUpdate);
    };
  });

  onDestroy(() => {
    if (refreshInterval) clearInterval(refreshInterval);
    if (ws) ws.close();
  });

  function connectWebSocket() {
    const wsUrl = API_URL.replace('http', 'ws') + '/ws/admin/sessions';
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('WebSocket connected for active sessions');
    };
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'session_update') {
        handleSessionUpdate(message.data);
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
      console.log('WebSocket closed, reconnecting in 5s...');
      setTimeout(connectWebSocket, 5000);
    };
  }

  function handleSessionUpdate(sessionData) {
    const existingIndex = activeSessions.findIndex(
      s => s.session_id === sessionData.session_id
    );
    
    if (sessionData.status === 'active') {
      if (existingIndex >= 0) {
        // Update existing session
        activeSessions[existingIndex] = {
          ...activeSessions[existingIndex],
          ...sessionData
        };
      } else {
        // Add new active session
        activeSessions = [sessionData, ...activeSessions];
      }
    } else if (sessionData.status === 'completed' || sessionData.status === 'failed') {
      // Remove from active sessions
      if (existingIndex >= 0) {
        activeSessions = activeSessions.filter(
          s => s.session_id !== sessionData.session_id
        );
      }
      // Refresh stats when session completes
      fetchStats();
    }
  }

  async function fetchDashboard() {
    loading = true;
    await Promise.all([
      fetchStats(),
      fetchUsers(),
      fetchRecentGenerations(),
      fetchActiveSessions(),
      fetchTasks(),
      fetchAllHistory()
    ]);
    loading = false;
  }

  async function fetchStats() {
    try {
      const res = await fetch(`${API_URL}/admin/dashboard`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) stats = await res.json();
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    }
  }

  async function fetchUsers() {
    try {
      const res = await fetch(`${API_URL}/admin/users-with-stats`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) users = await res.json();
    } catch (e) {
      console.error("Failed to fetch users:", e);
    }
  }

  async function fetchRecentGenerations() {
    try {
      const res = await fetch(`${API_URL}/admin/recent-generations?limit=10`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) recentGenerations = await res.json();
    } catch (e) {
      console.error("Failed to fetch recent generations:", e);
    }
  }

  async function fetchActiveSessions() {
    try {
      const res = await fetch(`${API_URL}/admin/active-sessions`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        // console.log("Active sessions received:", data);
        activeSessions = [...data];
      }
    } catch (e) {
      console.error("Failed to fetch active sessions:", e);
    }
  }

  async function fetchTasks() {
    try {
      const res = await fetch(`${API_URL}/tasks`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) tasks = await res.json();
    } catch (e) {
      console.error("Failed to fetch tasks:", e);
    }
  }

  async function fetchAllHistory() {
    try {
      const res = await fetch(`${API_URL}/admin/history`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) allHistory = await res.json();
    } catch (e) {
      console.error("Failed to fetch history:", e);
    }
  }

  async function createTask() {
    createError = "";
    try {
      const res = await fetch(`${API_URL}/tasks`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          ...newTask,
          assignee_id: parseInt(newTask.assignee_id),
          due_date: newTask.due_date ? new Date(newTask.due_date).toISOString() : null
        })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to create task");
      }
      showCreateTaskModal = false;
      newTask = {
        title: "",
        description: "",
        topic: "",
        num_questions: 5,
        num_sets: 1,
        difficulty: "medium",
        question_type: "multiple_choice",
        user_context: "",
        assignee_id: null,
        due_date: ""
      };
      await fetchTasks();
      await fetchStats();
      // Trigger update event
      window.dispatchEvent(new CustomEvent('statsUpdate'));
    } catch (e) {
      createError = e.message;
    }
  }

  async function createUser() {
    createError = "";
    try {
      const res = await fetch(`${API_URL}/users`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(newUser)
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to create user");
      }
      showCreateUserModal = false;
      newUser = { email: "", password: "" };
      await fetchUsers();
      await fetchStats();
      // Trigger update event
      window.dispatchEvent(new CustomEvent('statsUpdate'));
    } catch (e) {
      createError = e.message;
    }
  }

  async function deleteTask(taskId) {
    if (!confirm("Are you sure you want to delete this task?")) return;
    try {
      await fetch(`${API_URL}/tasks/${taskId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });
      await fetchTasks();
      await fetchStats();
      // Trigger update event
      window.dispatchEvent(new CustomEvent('statsUpdate'));
    } catch (e) {
      alert("Failed to delete task");
    }
  }

  async function toggleUserActive(userId) {
    try {
      await fetch(`${API_URL}/users/${userId}/toggle-active`, {
        method: "PUT",
        headers: { "Authorization": `Bearer ${token}` }
      });
      await fetchUsers();
      await fetchStats();
      // Trigger update event
      window.dispatchEvent(new CustomEvent('statsUpdate'));
    } catch (e) {
      alert("Failed to toggle user status");
    }
  }

  async function deleteUser(userId) {
    if (!confirm("Are you sure you want to delete this user?")) return;
    try {
      await fetch(`${API_URL}/users/${userId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });
      await fetchUsers();
      await fetchStats();
      // Trigger update event
      window.dispatchEvent(new CustomEvent('statsUpdate'));
    } catch (e) {
      alert("Failed to delete user");
    }
  }

  async function viewHistorySet(setId) {
    try {
      const res = await fetch(`${API_URL}/admin/history/${setId}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        selectedHistorySet = await res.json();
        showHistoryDetailModal = true;
      }
    } catch (e) {
      alert("Failed to load question set details");
    }
  }

  async function deleteHistorySet(setId) {
    if (!confirm("Are you sure you want to delete this question set? This action cannot be undone.")) return;
    try {
      const res = await fetch(`${API_URL}/admin/history/${setId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        await fetchAllHistory();
        await fetchStats();
        await fetchRecentGenerations();
        // Trigger update event
        window.dispatchEvent(new CustomEvent('statsUpdate'));
        if (showHistoryDetailModal) {
          showHistoryDetailModal = false;
          selectedHistorySet = null;
        }
      }
    } catch (e) {
      alert("Failed to delete question set");
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
      cancelled: "bg-gray-500",
      active: "bg-blue-500",
      failed: "bg-red-500"
    };
    return colors[status] || "bg-gray-500";
  }
</script>

<div class="container mx-auto p-4 md:p-6 max-w-7xl">
  <div class="mb-6">
    <h1 class="text-3xl font-bold">Admin Dashboard</h1>
    <p class="text-muted-foreground">Manage users, tasks, and monitor activity</p>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-20">
      <i class="fas fa-spinner fa-spin text-4xl text-primary"></i>
    </div>
  {:else}
    <!-- Stats Cards -->
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 md:gap-4 mb-6">
      <Card>
        <CardContent class="pt-6">
          <div class="text-2xl font-bold">{stats.total_users}</div>
          <p class="text-sm text-muted-foreground">Total Users</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-6">
          <div class="text-2xl font-bold text-green-500">{stats.active_users}</div>
          <p class="text-sm text-muted-foreground">Active Users</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-6">
          <div class="text-2xl font-bold">{stats.total_generations}</div>
          <p class="text-sm text-muted-foreground">Total Generations</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-6">
          <div class="text-2xl font-bold">{stats.total_questions}</div>
          <p class="text-sm text-muted-foreground">Total Questions</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-6">
          <div class="text-2xl font-bold text-blue-500">{stats.active_sessions}</div>
          <p class="text-sm text-muted-foreground">Active Sessions</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent class="pt-6">
          <div class="text-2xl font-bold text-yellow-500">{stats.pending_tasks}</div>
          <p class="text-sm text-muted-foreground">Pending Tasks</p>
        </CardContent>
      </Card>
    </div>

    <!-- Tabs -->
    <div class="flex gap-2 mb-6 overflow-x-auto pb-2 -mx-2 px-2 md:mx-0 md:px-0">
      <Button variant={activeTab === "overview" ? "default" : "outline"} onclick={() => activeTab = "overview"}>
        <i class="fas fa-chart-line mr-2"></i>Overview
      </Button>
      <Button variant={activeTab === "users" ? "default" : "outline"} onclick={() => activeTab = "users"}>
        <i class="fas fa-users mr-2"></i>Users
      </Button>
      <Button variant={activeTab === "tasks" ? "default" : "outline"} onclick={() => activeTab = "tasks"}>
        <i class="fas fa-tasks mr-2"></i>Tasks
      </Button>
      <Button variant={activeTab === "sessions" ? "default" : "outline"} onclick={() => activeTab = "sessions"}>
        <i class="fas fa-broadcast-tower mr-2"></i>Live Sessions
      </Button>      <Button variant={activeTab === "history" ? "default" : "outline"} onclick={() => activeTab = "history"}>
        <i class="fas fa-history mr-2"></i>History
      </Button>    </div>

    <!-- Overview Tab -->
    {#if activeTab === "overview"}
      <div class="grid grid-cols-1 gap-6">
        <!-- Recent Generations -->
        <Card>
          <CardHeader>
            <CardTitle class="flex items-center gap-2">
              <i class="fas fa-history"></i>
              Recent Generations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div class="space-y-3 max-h-96 overflow-y-auto">
              {#each recentGenerations as gen}
                <div class="p-3 bg-muted rounded-lg flex justify-between items-center">
                  <div>
                    <p class="font-medium">{gen.topic}</p>
                    <p class="text-sm text-muted-foreground">
                      by {gen.owner_email} • {gen.question_count} questions
                    </p>
                  </div>
                  <span class="text-xs text-muted-foreground">{formatDate(gen.created_at)}</span>
                </div>
              {:else}
                <p class="text-muted-foreground">No recent generations</p>
              {/each}
            </div>
          </CardContent>
        </Card>

        <!-- Active Sessions -->
        <Card>
          <CardHeader>
            <CardTitle class="flex items-center gap-2">
              <i class="fas fa-broadcast-tower text-green-500"></i>
              Live Sessions
              {#if activeSessions.length > 0}
                <span class="animate-pulse w-2 h-2 bg-green-500 rounded-full"></span>
              {/if}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div class="space-y-3 max-h-96 overflow-y-auto">
              {#each activeSessions as session}
                <div class="p-3 bg-muted rounded-lg">
                  <div class="flex justify-between items-start mb-2">
                    <div>
                      <p class="font-medium">{session.topic}</p>
                      <p class="text-sm text-muted-foreground">{session.user_email}</p>
                    </div>
                    <span class={`px-2 py-1 text-xs rounded-full text-white ${getStatusColor(session.status)}`}>
                      {session.status}
                    </span>
                  </div>
                  <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div class="bg-blue-500 h-2 rounded-full transition-all" style="width: {session.progress}%"></div>
                  </div>
                  <p class="text-xs text-muted-foreground mt-1">{session.current_step || 'Initializing...'}</p>
                </div>
              {:else}
                <p class="text-muted-foreground">No active sessions</p>
              {/each}
            </div>
          </CardContent>
        </Card>
      </div>
    {/if}

    <!-- Users Tab -->
    {#if activeTab === "users"}
      <Card>
        <CardHeader class="flex flex-row items-center justify-between">
          <CardTitle>Users</CardTitle>
          <Button onclick={() => { showCreateUserModal = true; createError = ""; }}>
            <i class="fas fa-plus mr-2"></i>Add User
          </Button>
        </CardHeader>
        <CardContent>
          <div class="overflow-x-auto">
            <table class="w-full">
              <thead>
                <tr class="border-b">
                  <th class="text-left p-3">Email</th>
                  <th class="text-left p-3">Status</th>
                  <th class="text-left p-3">Generations</th>
                  <th class="text-left p-3">Questions</th>
                  <th class="text-left p-3">Active Sessions</th>
                  <th class="text-left p-3">Pending Tasks</th>
                  <th class="text-left p-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {#each users as u}
                  <tr class="border-b hover:bg-muted/50">
                    <td class="p-3">
                      {u.email}
                      {#if u.is_admin}
                        <span class="ml-2 px-2 py-0.5 bg-purple-500 text-white text-xs rounded">Admin</span>
                      {/if}
                    </td>
                    <td class="p-3">
                      <span class={`px-2 py-1 text-xs rounded-full text-white ${u.is_active ? 'bg-green-500' : 'bg-red-500'}`}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td class="p-3">{u.total_generations}</td>
                    <td class="p-3">{u.total_questions}</td>
                    <td class="p-3">{u.active_sessions}</td>
                    <td class="p-3">{u.pending_tasks}</td>
                    <td class="p-3">
                      {#if !u.is_admin}
                        <div class="flex gap-2">
                          <Button size="sm" variant="outline" onclick={() => toggleUserActive(u.id)}>
                            {u.is_active ? 'Block' : 'Unblock'}
                          </Button>
                          <Button size="sm" variant="destructive" onclick={() => deleteUser(u.id)}>
                            <i class="fas fa-trash"></i>
                          </Button>
                        </div>
                      {:else}
                        <span class="text-muted-foreground text-sm">—</span>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    {/if}

    <!-- Tasks Tab -->
    {#if activeTab === "tasks"}
      <Card>
        <CardHeader class="flex flex-row items-center justify-between">
          <CardTitle>Tasks</CardTitle>
          <Button onclick={() => { showCreateTaskModal = true; createError = ""; }}>
            <i class="fas fa-plus mr-2"></i>Assign Task
          </Button>
        </CardHeader>
        <CardContent>
          <div class="space-y-4">
            {#each tasks as task}
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
                  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-sm mb-2">
                  <div><strong>Topic:</strong> {task.topic}</div>
                  <div><strong>Questions:</strong> {task.num_questions} × {task.num_sets} sets</div>
                  <div><strong>Difficulty:</strong> {task.difficulty}</div>
                  <div><strong>Assigned to:</strong> {task.assignee_email}</div>
                </div>
                <div class="flex justify-between items-center text-xs text-muted-foreground">
                  <span>Created by {task.created_by_email} on {formatDate(task.created_at)}</span>
                  {#if task.status === "pending"}
                    <Button size="sm" variant="destructive" onclick={() => deleteTask(task.id)}>
                      <i class="fas fa-trash mr-1"></i>Delete
                    </Button>
                  {/if}
                </div>
              </div>
            {:else}
              <p class="text-muted-foreground">No tasks created yet</p>
            {/each}
          </div>
        </CardContent>
      </Card>
    {/if}

    <!-- Live Sessions Tab -->
    {#if activeTab === "sessions"}
      <Card>
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <i class="fas fa-broadcast-tower"></i>
            Live Generation Sessions
            {#if activeSessions.length > 0}
              <span class="animate-pulse w-3 h-3 bg-green-500 rounded-full"></span>
            {/if}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {#if activeSessions.length > 0}
            <div class="space-y-4">
              {#each activeSessions as session}
                <div class="p-4 bg-muted rounded-lg">
                  <div class="flex justify-between items-start mb-3">
                    <div>
                      <h3 class="font-semibold text-lg">{session.topic}</h3>
                      <p class="text-sm text-muted-foreground">
                        Session: <code class="bg-background px-1 rounded">{session.session_id.substring(0, 8)}...</code>
                      </p>
                    </div>
                    <div class="text-right">
                      <span class={`px-3 py-1 text-sm rounded-full text-white ${getStatusColor(session.status)}`}>
                        {session.status}
                      </span>
                      <p class="text-sm text-muted-foreground mt-1">{session.user_email}</p>
                    </div>
                  </div>
                  <div class="mb-3">
                    <div class="flex justify-between text-sm mb-1">
                      <span>{session.current_step || 'Processing...'}</span>
                      <span>{session.progress}%</span>
                    </div>
                    <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                      <div class="bg-blue-500 h-3 rounded-full transition-all duration-500" style="width: {session.progress}%"></div>
                    </div>
                  </div>
                  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-sm text-muted-foreground">
                    <div><i class="fas fa-question-circle mr-1"></i>{session.num_questions} questions</div>
                    <div><i class="fas fa-layer-group mr-1"></i>{session.num_sets} sets</div>
                    <div><i class="fas fa-tachometer-alt mr-1"></i>{session.difficulty}</div>
                    <div><i class="fas fa-clock mr-1"></i>Started {formatDate(session.started_at)}</div>
                  </div>
                </div>
              {/each}
            </div>
          {:else}
            <div class="text-center py-10">
              <i class="fas fa-broadcast-tower text-4xl text-muted-foreground mb-4"></i>
              <p class="text-muted-foreground">No active generation sessions</p>
              <p class="text-sm text-muted-foreground">Sessions will appear here when users start generating questions</p>
            </div>
          {/if}
        </CardContent>
      </Card>
    {/if}

    <!-- History Tab -->
    {#if activeTab === "history"}
      <Card>
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <i class="fas fa-history"></i>
            All Generation History
            <span class="text-sm font-normal text-muted-foreground">({allHistory.length} sets)</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {#if allHistory.length > 0}
            <div class="space-y-3 max-h-[600px] overflow-y-auto">
              {#each allHistory as historySet}
                <div class="p-4 bg-muted rounded-lg">
                  <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-3">
                    <div class="flex-1">
                      <h3 class="font-semibold text-lg">{historySet.topic}</h3>
                      <div class="flex flex-wrap gap-3 text-sm text-muted-foreground mt-1">
                        <span><i class="fas fa-user mr-1"></i>{historySet.owner_email}</span>
                        <span><i class="fas fa-question-circle mr-1"></i>{historySet.question_count} questions</span>
                        <span><i class="fas fa-tachometer-alt mr-1"></i>{historySet.difficulty}</span>
                        <span><i class="fas fa-clock mr-1"></i>{formatDate(historySet.created_at)}</span>
                      </div>
                    </div>
                    <div class="flex gap-2">
                      <Button size="sm" variant="outline" onclick={() => viewHistorySet(historySet.id)}>
                        <i class="fas fa-eye mr-1"></i>View
                      </Button>
                      <Button size="sm" variant="destructive" onclick={() => deleteHistorySet(historySet.id)}>
                        <i class="fas fa-trash mr-1"></i>Delete
                      </Button>
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          {:else}
            <div class="text-center py-10">
              <i class="fas fa-history text-4xl text-muted-foreground mb-4"></i>
              <p class="text-muted-foreground">No generation history found</p>
              <p class="text-sm text-muted-foreground">History will appear when users generate questions</p>
            </div>
          {/if}
        </CardContent>
      </Card>
    {/if}
  {/if}

  <!-- Create Task Modal -->
  {#if showCreateTaskModal}
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card class="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <CardTitle>Assign New Task</CardTitle>
        </CardHeader>
        <CardContent>
          {#if createError}
            <div class="bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 p-3 rounded mb-4">
              {createError}
            </div>
          {/if}
          <form onsubmit={(e) => { e.preventDefault(); createTask(); }} class="space-y-4">
            <div>
              <Label>Title</Label>
              <Input bind:value={newTask.title} required placeholder="e.g., Generate Math Questions" />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea bind:value={newTask.description} placeholder="Task details..." />
            </div>
            <div>
              <Label>Assign To</Label>
              <Select bind:value={newTask.assignee_id} required>
                <option value="">Select user...</option>
                {#each users.filter(u => !u.is_admin) as u}
                  <option value={u.id}>{u.email}</option>
                {/each}
              </Select>
            </div>
            <div>
              <Label>Topic</Label>
              <Input bind:value={newTask.topic} required placeholder="e.g., Algebra" />
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label>Questions per Set</Label>
                <Input type="number" bind:value={newTask.num_questions} min="1" max="50" />
              </div>
              <div>
                <Label>Number of Sets</Label>
                <Input type="number" bind:value={newTask.num_sets} min="1" max="10" />
              </div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label>Difficulty</Label>
                <Select bind:value={newTask.difficulty}>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </Select>
              </div>
              <div>
                <Label>Question Type</Label>
                <Select bind:value={newTask.question_type}>
                  <option value="multiple_choice">Multiple Choice</option>
                  <option value="true_false">True/False</option>
                  <option value="short_answer">Short Answer</option>
                </Select>
              </div>
            </div>
            <div>
              <Label>Additional Context (Optional)</Label>
              <Textarea bind:value={newTask.user_context} placeholder="Special instructions..." />
            </div>
            <div>
              <Label>Due Date (Optional)</Label>
              <Input type="datetime-local" bind:value={newTask.due_date} />
            </div>
            <div class="flex gap-2 justify-end">
              <Button type="button" variant="outline" onclick={() => showCreateTaskModal = false}>Cancel</Button>
              <Button type="submit">Create Task</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  {/if}

  <!-- Create User Modal -->
  {#if showCreateUserModal}
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card class="w-full max-w-md">
        <CardHeader>
          <CardTitle>Add New User</CardTitle>
        </CardHeader>
        <CardContent>
          {#if createError}
            <div class="bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 p-3 rounded mb-4">
              {createError}
            </div>
          {/if}
          <form onsubmit={(e) => { e.preventDefault(); createUser(); }} class="space-y-4">
            <div>
              <Label>Email</Label>
              <Input type="email" bind:value={newUser.email} required placeholder="user@example.com" />
            </div>
            <div>
              <Label>Password</Label>
              <Input type="password" bind:value={newUser.password} required placeholder="••••••••" />
            </div>
            <div class="flex gap-2 justify-end">
              <Button type="button" variant="outline" onclick={() => showCreateUserModal = false}>Cancel</Button>
              <Button type="submit">Create User</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  {/if}

  <!-- History Detail Modal -->
  {#if showHistoryDetailModal && selectedHistorySet}
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <Card class="w-full max-w-4xl my-8 max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <div class="flex items-start justify-between">
            <div>
              <CardTitle class="text-2xl">{selectedHistorySet.topic}</CardTitle>
              <div class="flex flex-wrap gap-3 text-sm text-muted-foreground mt-2">
                <span><i class="fas fa-user mr-1"></i>{selectedHistorySet.owner_email}</span>
                <span><i class="fas fa-question-circle mr-1"></i>{selectedHistorySet.question_count} questions</span>
                <span><i class="fas fa-tachometer-alt mr-1"></i>{selectedHistorySet.difficulty}</span>
                <span><i class="fas fa-clock mr-1"></i>{formatDate(selectedHistorySet.created_at)}</span>
              </div>
            </div>
            <Button variant="ghost" size="sm" onclick={() => { showHistoryDetailModal = false; selectedHistorySet = null; }}>
              <i class="fas fa-times text-lg"></i>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div class="space-y-4">
            {#each selectedHistorySet.questions as question, idx}
              <div class="p-4 bg-background border rounded-lg">
                <div class="flex justify-between items-start mb-3">
                  <h4 class="font-semibold">Question {idx + 1}</h4>
                </div>
                <p class="mb-3 text-foreground">{question.description}</p>
                <div class="space-y-2 mb-3">
                  {#each question.options as option, optIdx}
                    <div class="flex items-center gap-2 p-2 rounded {option === question.answer ? 'bg-green-500/10 border border-green-500/30' : 'bg-muted'}">
                      <span class="font-semibold">{String.fromCharCode(65 + optIdx)}.</span>
                      <span class={option === question.answer ? 'text-green-600 dark:text-green-400 font-medium' : ''}>{option}</span>
                      {#if option === question.answer}
                        <i class="fas fa-check-circle text-green-500 ml-auto"></i>
                      {/if}
                    </div>
                  {/each}
                </div>
                {#if question.explanation}
                  <div class="p-3 bg-blue-500/10 border border-blue-500/30 rounded">
                    <p class="text-sm"><strong>Explanation:</strong> {question.explanation}</p>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
          <div class="flex gap-2 justify-end mt-6 pt-4 border-t">
            <Button variant="destructive" onclick={() => deleteHistorySet(selectedHistorySet.id)}>
              <i class="fas fa-trash mr-2"></i>Delete This Set
            </Button>
            <Button variant="outline" onclick={() => { showHistoryDetailModal = false; selectedHistorySet = null; }}>
              Close
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  {/if}
</div>
