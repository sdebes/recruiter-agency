import React from 'react';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import SidebarWrapper from './SidebarWrapper';
import { NotificationProvider } from '@/context/NotificationContext';
import { PipelineProvider } from '@/context/PipelineContext';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });

export const metadata: Metadata = {
  title: 'Recruiter Agency — AI-powered job search',
  description: 'Find, evaluate, and track job opportunities using LangGraph and Gemini.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable}`}>
      <body className="bg-slate-50 text-slate-900 font-sans min-h-screen">
        <NotificationProvider>
          <PipelineProvider>
            <div className="flex">
              {/* Sidebar */}
              <SidebarWrapper />

              {/* Main Workspace */}
              <main className="flex-1 ml-64 min-h-screen p-8 transition-all duration-300">
                {children}
              </main>
            </div>
          </PipelineProvider>
        </NotificationProvider>
      </body>
    </html>
  );
}
