<script>
	import { cn } from "$lib/utils";
	let { class: className = "", children, ...rest } = $props();
</script>

<h3
	class={cn(
		"text-2xl font-semibold leading-none tracking-tight",
		className
	)}
	{...rest}
>
	{@render children?.()}
</h3>
