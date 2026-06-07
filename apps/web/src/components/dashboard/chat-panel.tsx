import { Bot, Sparkles } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useForm } from "react-hook-form";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { motion, AnimatePresence } from "framer-motion";

import { IconButton } from "@/components/ui/icon-button";
import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace-store";
import type { Repository } from "@/types/api";

import { LoaderLine, Panel } from "./shared";

const chatSchema = z.object({
  message: z.string().min(2).max(8000)
});
type ChatForm = z.infer<typeof chatSchema>;

export function ChatPanel({ repository }: { repository: Repository | null }) {
  const conversationId = useWorkspaceStore((state) => state.conversationId);
  const setConversationId = useWorkspaceStore((state) => state.setConversationId);
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  
  const form = useForm<ChatForm>({
    resolver: zodResolver(chatSchema),
    defaultValues: { message: "" }
  });
  
  const chatMutation = useMutation({
    mutationFn: api.chat,
    onSuccess: (response) => {
      setConversationId(response.conversation_id);
      setMessages((current) => [...current, { role: "assistant", content: response.answer }]);
    }
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatMutation.isPending]);

  return (
    <Panel title="AI Code Chat" icon={Bot}>
      <div className="mb-4 h-64 overflow-y-auto rounded-lg border border-border/50 bg-black/5 dark:bg-white/5 p-4 flex flex-col gap-3">
        {messages.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-sm text-muted-foreground italic">Ask about the selected codebase.</p>
          </div>
        ) : null}
        
        <AnimatePresence>
          {messages.map((message, index) => (
            <motion.div 
              initial={{ opacity: 0, y: 10, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              key={`${message.role}-${index}`} 
              className={`max-w-[85%] p-3 rounded-2xl ${
                message.role === "user" 
                  ? "bg-accent text-accent-foreground self-end rounded-br-sm" 
                  : "bg-white dark:bg-black border border-border self-start rounded-bl-sm"
              }`}
            >
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {chatMutation.isPending ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="self-start p-3 bg-white dark:bg-black border border-border rounded-2xl rounded-bl-sm">
            <LoaderLine label="Thinking..." />
          </motion.div>
        ) : null}
        
        <div ref={bottomRef} />
      </div>
      
      <form
        className="flex gap-3"
        onSubmit={form.handleSubmit((value) => {
          if (!repository) return;
          setMessages((current) => [...current, { role: "user", content: value.message }]);
          chatMutation.mutate({
            repository_id: repository.id,
            message: value.message,
            ...(conversationId ? { conversation_id: conversationId } : {})
          });
          form.reset({ message: "" });
        })}
      >
        <input 
          className="glass-input h-10 min-w-0 flex-1 rounded-full px-5 text-sm" 
          placeholder="Type your message..."
          {...form.register("message")} 
        />
        <IconButton 
          icon={Sparkles} 
          label="Send" 
          disabled={!repository || chatMutation.isPending} 
          type="submit" 
          className="rounded-full w-10 h-10 p-0 justify-center bg-accent hover:bg-accent/90 text-white" 
        />
      </form>
    </Panel>
  );
}
