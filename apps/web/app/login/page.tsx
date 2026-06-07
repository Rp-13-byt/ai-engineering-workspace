"use client";

import { Github, LogIn } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { IconButton } from "@/components/ui/icon-button";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1)
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" }
  });
  const loginMutation = useMutation({
    mutationFn: api.login,
    onSuccess: (response) => {
      window.localStorage.setItem("workspace.accessToken", response.access_token);
      window.localStorage.setItem("workspace.refreshToken", response.refresh_token);
      window.localStorage.setItem("workspace.organizationId", response.organization.id);
      router.push("/");
    }
  });

  return (
    <main className="grid min-h-screen place-items-center bg-background p-6 text-foreground">
      <section className="w-full max-w-sm border border-border bg-panel p-6">
        <h1 className="mb-6 text-xl font-semibold">Sign in</h1>
        <form className="space-y-4" onSubmit={form.handleSubmit((value) => loginMutation.mutate(value))}>
          <label className="block text-sm font-medium">
            Email
            <input
              className="mt-2 h-10 w-full border border-border bg-background px-3 text-sm"
              type="email"
              autoComplete="email"
              {...form.register("email")}
            />
          </label>
          <label className="block text-sm font-medium">
            Password
            <input
              className="mt-2 h-10 w-full border border-border bg-background px-3 text-sm"
              type="password"
              autoComplete="current-password"
              {...form.register("password")}
            />
          </label>
          <div className="flex gap-2">
            <IconButton icon={LogIn} label={loginMutation.isPending ? "Signing in" : "Sign in"} type="submit" />
            <IconButton icon={Github} label="GitHub" variant="secondary" type="button" />
          </div>
          {loginMutation.error ? <p className="text-sm text-danger">Sign in failed.</p> : null}
        </form>
      </section>
    </main>
  );
}
