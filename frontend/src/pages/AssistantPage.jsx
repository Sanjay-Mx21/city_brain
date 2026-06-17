import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Bot, Loader2, Send, Ticket, PlusCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import { assistantAPI } from '../services/api';
import { useAuth } from '../utils/AuthContext';

export default function AssistantPage() {
  const { user } = useAuth();
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Tell me the civic issue you want to report, or send a ticket ID like CB-2026-00001.',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;

    setMessages((prev) => [...prev, { role: 'user', text }]);
    setInput('');
    setLoading(true);
    try {
      const { data } = await assistantAPI.chat({
        message: text,
        language: user?.preferred_language || 'en',
      });
      setMessages((prev) => [...prev, { role: 'assistant', text: data.reply, data }]);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Assistant failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-3 rounded-lg bg-brand-600 text-white">
          <Bot className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">City Brain Assistant</h1>
          <p className="text-slate-500">Guided complaint filing and ticket status help</p>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl min-h-[420px] flex flex-col">
        <div className="flex-1 p-4 space-y-3 overflow-y-auto">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-lg px-4 py-3 text-sm ${
                  message.role === 'user'
                    ? 'bg-brand-600 text-white'
                    : 'bg-slate-100 text-slate-700'
                }`}
              >
                {message.text}
                {message.data?.suggested_action === 'submit' && (
                  <div className="mt-3">
                    <Link to="/submit" className="inline-flex items-center gap-1 text-xs font-medium underline">
                      <PlusCircle className="w-3 h-3" /> Open complaint form
                    </Link>
                  </div>
                )}
                {message.data?.ticket_id && (
                  <div className="mt-3">
                    <Link to={`/track/${message.data.ticket_id}`} className="inline-flex items-center gap-1 text-xs font-medium underline">
                      <Ticket className="w-3 h-3" /> Open ticket
                    </Link>
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="w-4 h-4 animate-spin" />
              Assistant is checking...
            </div>
          )}
        </div>

        <form onSubmit={sendMessage} className="border-t border-slate-200 p-3 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask for help or enter a ticket ID"
            className="flex-1 px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500 outline-none text-sm"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 rounded-lg bg-brand-600 text-white disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
          </button>
        </form>
      </div>
    </div>
  );
}
