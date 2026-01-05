<script>
  import { authState, logout } from "../stores/auth";
  import { navigate, route } from "../stores/router";
  import { theme } from "../stores/theme";
  import { Button } from "$lib/components/ui/button";

  let isAuthenticated;
  let currentRoute;
  let user;
  let currentTheme;
  let mobileMenuOpen = false;

  authState.subscribe(value => {
    isAuthenticated = value.isAuthenticated;
    user = value.user;
  });

  route.subscribe(value => {
    currentRoute = value;
    mobileMenuOpen = false; // Close menu on route change
  });

  theme.subscribe(value => {
    currentTheme = value;
  });

  function handleLogout() {
    logout();
    navigate("/login");
  }

  function toggleMobileMenu() {
    mobileMenuOpen = !mobileMenuOpen;
  }
</script>

<header class="border-b bg-background sticky top-0 z-50 w-full shadow-sm">
  <div class="container flex h-16 items-center justify-between px-4 md:px-8 max-w-7xl mx-auto">
    <div class="flex items-center gap-4">
      <a href="/" onclick={(e) => { e.preventDefault(); navigate("/dashboard"); }} class="flex items-center space-x-2">
        <span class="font-bold text-xl md:text-2xl tracking-tight text-primary">QGen</span>
      </a>
      
      {#if isAuthenticated}
        <nav class="hidden md:flex items-center gap-6 text-sm font-medium">
          <a 
            href="/dashboard" 
            onclick={(e) => { e.preventDefault(); navigate("/dashboard"); }} 
            class="transition-colors hover:text-foreground/80 {currentRoute === '/dashboard' || currentRoute === '/' ? 'text-foreground' : 'text-foreground/60'}"
          >
            Dashboard
          </a>
          <a 
            href="/generate" 
            onclick={(e) => { e.preventDefault(); navigate("/generate"); }} 
            class="transition-colors hover:text-foreground/80 {currentRoute === '/generate' ? 'text-foreground' : 'text-foreground/60'}"
          >
            Generate
          </a>
          <a 
            href="/history" 
            onclick={(e) => { e.preventDefault(); navigate("/history"); }} 
            class="transition-colors hover:text-foreground/80 {currentRoute === '/history' ? 'text-foreground' : 'text-foreground/60'}"
          >
            History
          </a>
          {#if user?.is_admin}
            <a 
              href="/admin" 
              onclick={(e) => { e.preventDefault(); navigate("/admin"); }} 
              class="transition-colors hover:text-foreground/80 {currentRoute === '/admin' ? 'text-foreground' : 'text-foreground/60'}"
            >
              Users
            </a>
          {/if}
        </nav>
      {/if}
    </div>

    <div class="flex items-center gap-2 md:gap-4">
      <Button 
        variant="ghost" 
        size="sm" 
        onclick={() => theme.toggleTheme()}
        class="gap-2 h-9 w-9 p-0 md:h-10 md:w-auto md:px-4"
        title={currentTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {#if currentTheme === 'dark'}
          <i class="fas fa-sun"></i>
        {:else}
          <i class="fas fa-moon"></i>
        {/if}
      </Button>
      {#if isAuthenticated}
        <Button variant="outline" size="sm" onclick={handleLogout} class="hidden md:inline-flex">Logout</Button>
        <Button 
          variant="ghost" 
          size="sm" 
          onclick={toggleMobileMenu}
          class="md:hidden h-9 w-9 p-0"
          aria-label="Toggle menu"
        >
          <i class="fas {mobileMenuOpen ? 'fa-times' : 'fa-bars'} text-lg"></i>
        </Button>
      {/if}
    </div>
  </div>

  <!-- Mobile Menu -->
  {#if isAuthenticated && mobileMenuOpen}
    <div class="md:hidden border-t bg-background">
      <nav class="container mx-auto px-4 py-4 flex flex-col gap-3">
        <a 
          href="/dashboard" 
          onclick={(e) => { e.preventDefault(); navigate("/dashboard"); }} 
          class="px-4 py-3 rounded-md transition-colors hover:bg-muted {currentRoute === '/dashboard' || currentRoute === '/' ? 'bg-muted text-foreground font-semibold' : 'text-foreground/60'}"
        >
          <i class="fas fa-home mr-3 w-5"></i>Dashboard
        </a>
        <a 
          href="/generate" 
          onclick={(e) => { e.preventDefault(); navigate("/generate"); }} 
          class="px-4 py-3 rounded-md transition-colors hover:bg-muted {currentRoute === '/generate' ? 'bg-muted text-foreground font-semibold' : 'text-foreground/60'}"
        >
          <i class="fas fa-plus-circle mr-3 w-5"></i>Generate
        </a>
        <a 
          href="/history" 
          onclick={(e) => { e.preventDefault(); navigate("/history"); }} 
          class="px-4 py-3 rounded-md transition-colors hover:bg-muted {currentRoute === '/history' ? 'bg-muted text-foreground font-semibold' : 'text-foreground/60'}"
        >
          <i class="fas fa-history mr-3 w-5"></i>History
        </a>
        {#if user?.is_admin}
          <a 
            href="/admin" 
            onclick={(e) => { e.preventDefault(); navigate("/admin"); }} 
            class="px-4 py-3 rounded-md transition-colors hover:bg-muted {currentRoute === '/admin' ? 'bg-muted text-foreground font-semibold' : 'text-foreground/60'}"
          >
            <i class="fas fa-users-cog mr-3 w-5"></i>Users
          </a>
        {/if}
        <div class="border-t pt-3 mt-2">
          <button 
            onclick={handleLogout}
            class="w-full px-4 py-3 rounded-md transition-colors hover:bg-destructive/10 text-destructive font-medium text-left"
          >
            <i class="fas fa-sign-out-alt mr-3 w-5"></i>Logout
          </button>
        </div>
      </nav>
    </div>
  {/if}
</header>
