<script>
  import { navigate } from "../stores/router";
  import { login } from "../stores/auth";
  import { API_URL } from "../config/api";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Label } from "$lib/components/ui/label";
  import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "$lib/components/ui/card";

  let email = "";
  let password = "";
  let loading = false;
  let error = "";

  async function handleLogin(e) {
    if (e) e.preventDefault();
    loading = true;
    error = "";
    try {
      const formData = new FormData();
      formData.append("username", email);
      formData.append("password", password);

      const res = await fetch(`${API_URL}/token`, {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Login failed");
      }

      const data = await res.json();
      const token = data.access_token;

      // Fetch user details
      const userRes = await fetch(`${API_URL}/users/me`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      const user = await userRes.json();

      login(token, user);
      navigate("/");
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="flex flex-col items-center justify-start min-h-screen pt-12 px-4">
  <div class="text-center mb-8">
    <div class="text-4xl md:text-5xl lg:text-6xl font-extrabold tracking-tight">QGen</div>
  </div>
  <Card class="w-full max-w-md mt-2">
    <CardHeader>
      <CardTitle class="text-xl md:text-2xl text-center">Welcome Back</CardTitle>
      <p class="text-center text-sm text-muted-foreground">Login to your account</p>
    </CardHeader>
    <CardContent>
      <form onsubmit={handleLogin} class="space-y-4">
        <div class="space-y-2">
          <Label for="email">Email</Label>
          <Input id="email" name="username" type="email" autocomplete="email" bind:value={email} required placeholder="m@example.com" />
        </div>
        <div class="space-y-2">
          <Label for="password">Password</Label>
          <Input id="password" name="password" type="password" autocomplete="current-password" bind:value={password} required />
        </div>

        {#if error}
          <div class="text-sm text-destructive bg-destructive/10 p-3 rounded-md">
            {error}
          </div>
        {/if}

        <Button type="submit" class="w-full" disabled={loading}>
          {loading ? "Logging in..." : "Login"}
        </Button>
      </form>
    </CardContent>
  </Card>
</div>
