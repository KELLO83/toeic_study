"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"

export default function SidebarLayout({
    children,
}: {
    children: React.ReactNode
}) {
    const [isCollapsed, setIsCollapsed] = useState(false)
    const pathname = usePathname()

    // 모바일 화면 등에서 초기 상태 조정을 원하면 useEffect 사용 가능
    // 여기서는 간단하게 토글 기능만 구현

    return (
        <div className="flex min-h-screen">
            {/* Sidebar Navigation */}
            <aside
                className={`${isCollapsed ? "w-20" : "w-64"
                    } bg-white dark:bg-[#161b22] border-r border-slate-200 dark:border-[#30363d] fixed h-full flex flex-col z-20 transition-all duration-300 ease-in-out shadow-sm`}
            >
                {/* Logo Area */}
                <div className="p-4 h-20 flex items-center justify-between border-b border-slate-100 dark:border-[#30363d]">
                    <div className={`flex items-center gap-2 text-indigo-600 dark:text-indigo-400 overflow-hidden whitespace-nowrap transition-all duration-300 ${isCollapsed ? "w-0 opacity-0 px-0" : "w-auto opacity-100"}`}>
                        <span className="text-2xl min-w-[24px]">⚡</span>
                        <span className="font-extrabold text-xl tracking-tight">TOEIC Whisper</span>
                    </div>
                    <div className={`${isCollapsed ? "w-full flex justify-center" : ""}`}>
                        {isCollapsed && <span className="text-2xl mb-2">⚡</span>}
                        <button
                            onClick={() => setIsCollapsed(!isCollapsed)}
                            className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                        >
                            {isCollapsed ? "➡️" : "⬅️"}
                        </button>
                    </div>
                </div>

                {/* Navigation Links */}
                <nav className="flex-1 p-3 space-y-2 mt-2 overflow-hidden">
                    <Link
                        href="/"
                        className={`flex items-center gap-3 px-3 py-3 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-indigo-600 dark:hover:text-indigo-400 rounded-xl transition-all group font-semibold whitespace-nowrap ${pathname === "/" ? "bg-indigo-50 dark:bg-slate-800 text-indigo-700 dark:text-indigo-300" : ""}`}
                        title="Vocabulary"
                    >
                        <span className="text-xl group-hover:scale-110 transition-transform min-w-[24px] text-center">📚</span>
                        <span className={`transition-opacity duration-300 ${isCollapsed ? "opacity-0 w-0 hidden" : "opacity-100"}`}>Vocabulary</span>
                    </Link>
                    <Link
                        href="/lc"
                        className={`flex items-center gap-3 px-3 py-3 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-indigo-600 dark:hover:text-indigo-400 rounded-xl transition-all group font-semibold whitespace-nowrap ${pathname === "/lc" ? "bg-indigo-50 dark:bg-slate-800 text-indigo-700 dark:text-indigo-300" : ""}`}
                        title="Listening"
                    >
                        <span className="text-xl group-hover:scale-110 transition-transform min-w-[24px] text-center">🎧</span>
                        <span className={`transition-opacity duration-300 ${isCollapsed ? "opacity-0 w-0 hidden" : "opacity-100"}`}>Listening</span>
                    </Link>
                </nav>

                {/* Footer / Version Info */}
                <div className="p-4 border-t border-slate-100 dark:border-[#30363d]">
                    <div className={`flex items-center gap-3 p-2 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-700/50 overflow-hidden whitespace-nowrap transition-all duration-300 ${isCollapsed ? "justify-center px-0 bg-transparent border-0" : ""}`}>
                        <div className="w-8 h-8 min-w-[32px] rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center text-indigo-600 dark:text-indigo-400 text-xs font-bold">
                            JS
                        </div>
                        <div className={`flex-1 transition-opacity duration-300 ${isCollapsed ? "opacity-0 w-0 hidden" : "opacity-100"}`}>
                            <p className="text-xs font-bold text-slate-700 dark:text-slate-200">User Profile</p>
                            <p className="text-[10px] text-slate-400">Level 1 • Learner</p>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content Area */}
            <main className={`flex-1 p-4 min-h-screen transition-all duration-300 ease-in-out ${isCollapsed ? "ml-20" : "ml-64"}`}>
                <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {children}
                </div>
            </main>

        </div>
    )
}
