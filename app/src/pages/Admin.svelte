<script>
  import { authState } from "../stores/auth";
  import { onMount } from "svelte";
  import { navigate } from "../stores/router";
  import { API_URL } from "../config/api";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Card, CardHeader, CardTitle, CardContent } from "$lib/components/ui/card";

  let token;
  authState.subscribe(v => token = v.token);

  let users = [];
  let loading = true;
  let newUserEmail = "";
  let newUserPassword = "";
  let creating = false;
  let error = "";

  async function fetchUsers() {
    try {
      const res = await fetch(`${API_URL}/users`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) users = await res.json();
      else if (res.status === 403) navigate("/"); // Not admin
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  }

  async function createUser() {
    creating = true; error = "";
    try {
      const res = await fetch(`${API_URL}/users`, {
        method: "POST",
        headers: { 
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ email: newUserEmail, password: newUserPassword })
      });
      if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail);
      }
      newUserEmail = ""; newUserPassword = "";
      fetchUsers();
    } catch (e) { error = e.message; }
    finally { creating = false; }
  }

  async function toggleActive(id) {
    try {
      await fetch(`${API_URL}/users/${id}/toggle-active`, {
        method: "PUT",
        headers: { "Authorization": `Bearer ${token}` }
      });
      fetchUsers();
    } catch (e) { alert(e.message); }
  }

  async function deleteUser(id) {
    if(!confirm("Are you sure?")) return;
    try {
      await fetch(`${API_URL}/users/${id}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });
      fetchUsers();
    } catch (e) { alert(e.message); }
  }

  onMount(() => {
    if (!token) navigate("/login");
    else fetchUsers();
  });
</script>

<div class="py-8 max-w-5xl mx-auto">  
  <Card class="mb-8">
    <CardHeader>
      <CardTitle>Add New User</CardTitle>
    </CardHeader>
    <CardContent>
      <form on:submit|preventDefault={createUser} class="flex gap-4 items-end">
          <div class="flex-1 space-y-2">
            <Input type="email" name="email" autocomplete="email" bind:value={newUserEmail} placeholder="Email address" />
          </div>
          <div class="flex-1 space-y-2">
            <Input type="password" name="password" autocomplete="new-password" bind:value={newUserPassword} placeholder="Password" />
          </div>
          <Button type="submit" disabled={creating}>Add User</Button>
      </form>
      {#if error} 
        <div class="mt-4 text-sm text-destructive bg-destructive/10 p-3 rounded-md">{error}</div> 
      {/if}
    </CardContent>
  </Card>

  {#if loading}
    <div class="flex items-center justify-center h-64 text-muted-foreground">Loading users...</div>
  {:else}
    <div class="border rounded-lg overflow-hidden bg-card text-card-foreground shadow-sm">
      <table class="w-full text-sm text-left">
          <thead class="bg-muted text-muted-foreground uppercase text-xs font-medium">
              <tr>
                  <th class="px-6 py-4">ID</th>
                  <th class="px-6 py-4">Email</th>
                  <th class="px-6 py-4">Status</th>
                  <th class="px-6 py-4 text-right">Actions</th>
              </tr>
          </thead>
          <tbody class="divide-y divide-border">
              {#each users as user}
                  <tr class="hover:bg-muted/50 transition-colors">
                      <td class="px-6 py-4 font-medium">{user.id}</td>
                      <td class="px-6 py-4">{user.email}</td>
                      <td class="px-6 py-4">
                          <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold
                              {user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                              {user.is_active ? 'Active' : 'Blocked'}
                          </span>
                      </td>
                      <td class="px-6 py-4 text-right space-x-2">
                          <Button variant="outline" size="sm" onclick={() => toggleActive(user.id)}>
                              {user.is_active ? 'Block' : 'Unblock'}
                          </Button>
                          <Button variant="destructive" size="sm" onclick={() => deleteUser(user.id)}>Delete</Button>
                      </td>
                  </tr>
              {/each}
          </tbody>
      </table>
    </div>
  {/if}
</div>