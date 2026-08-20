import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { DailyTaskGenerator } from "@/components/daily-task-generator";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Jidoka",
  description: "Kanban board operated by you and an LLM agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('theme') || 'system';
                  var dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                  var resolved = theme === 'system' ? (dark ? 'dark' : 'light') : theme;
                  var html = document.documentElement;
                  html.classList.remove('light', 'dark');
                  html.classList.add(resolved);
                  html.style.colorScheme = resolved;
                } catch (e) {}
              })();
            `,
          }}
        />
        <ThemeProvider defaultTheme="system">
          {children}
          <Toaster />
          <DailyTaskGenerator />
        </ThemeProvider>
      </body>
    </html>
  );
}
