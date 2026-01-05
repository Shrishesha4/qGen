<script>
  import { onMount } from "svelte";
  import Navbar from "./lib/Navbar.svelte";
  import Login from "./pages/Login.svelte";
  import Dashboard from "./pages/Dashboard.svelte";
  import History from "./pages/History.svelte";
  import Admin from "./pages/Admin.svelte";
  import AdminDashboard from "./pages/AdminDashboard.svelte";
  import UserDashboard from "./pages/UserDashboard.svelte";
  import { route, navigate } from "./stores/router";
  import { theme } from "./stores/theme";
  import { authState } from "./stores/auth";

  let currentRoute;
  let user = null;
  let token = null;
  
  route.subscribe(value => {
    currentRoute = value;
  });

  authState.subscribe(value => {
    user = value.user;
    token = value.token;
  });

  // Initialize theme on mount
  onMount(() => {
    // Theme is already initialized in the store
    // Subscribe to keep the store reactive
    const unsubscribe = theme.subscribe(() => {});
    return unsubscribe;
  });

  // Watch for auth changes and redirect accordingly
  $: {
    // Auth redirects are now handled in the router store
  }
</script>

<div class="min-h-screen bg-background font-sans antialiased">
  {#if currentRoute !== '/login'}
    <Navbar />
  {/if}
  <main class="container mx-auto px-3 sm:px-4 md:px-8 max-w-7xl">
    {#if currentRoute === '/login'}
      <Login />
    {:else if currentRoute === '/dashboard'}
      {#if user?.is_admin}
        <AdminDashboard />
      {:else}
        <UserDashboard />
      {/if}
    {:else if currentRoute === '/generate'}
      <Dashboard />
    {:else if currentRoute === '/history'}
      <History />
    {:else if currentRoute === '/admin'}
      <Admin />
    {:else}
      {#if user?.is_admin}
        <AdminDashboard />
      {:else}
        <UserDashboard />
      {/if}
    {/if}
  </main>
</div>