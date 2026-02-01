"use client"

import { useEffect, useState, useRef } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

// Define Word Type
interface Word {
  id: number
  word: string
  meaning: string
  sheet_name: string
}

interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

export default function Home() {
  const [words, setWords] = useState<Word[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")

  // Design & Study Mode State
  const [isStudyMode, setIsStudyMode] = useState(false)
  const [isDarkMode, setIsDarkMode] = useState(true) // Default Dark Mode
  const [revealedIds, setRevealedIds] = useState<number[]>([])

  // Pagination State
  const [itemsPerPage, setItemsPerPage] = useState(10)
  const [currentPage, setCurrentPage] = useState(1)

  // Chat State
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [chatMessage, setChatMessage] = useState("")
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const [isChatLoading, setIsChatLoading] = useState(false)
  const chatScrollRef = useRef<HTMLDivElement>(null)

  // Auto scroll chat
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
    }
  }, [chatHistory])

  // Clear revealed words when study mode changes
  useEffect(() => {
    if (isStudyMode) {
      setRevealedIds([])
    }
  }, [isStudyMode])

  const toggleReveal = (id: number) => {
    if (!isStudyMode) return

    if (revealedIds.includes(id)) {
      setRevealedIds(prev => prev.filter(i => i !== id))
    } else {
      setRevealedIds(prev => [...prev, id])
    }
  }

  // Load Theme
  useEffect(() => {
    const saved = localStorage.getItem("theme")
    if (saved === "light") setIsDarkMode(false)
  }, [])

  // Toggle Dark Mode Class
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add("dark")
      localStorage.setItem("theme", "dark")
    } else {
      document.documentElement.classList.remove("dark")
      localStorage.setItem("theme", "light")
    }
  }, [isDarkMode])

  // TTS State
  const [accent, setAccent] = useState<"US" | "UK" | "AU">("US")
  const [playingId, setPlayingId] = useState<number | null>(null)

  // Refs for tracking playback to allow cancellation
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  const stopCurrentAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
  }

  const playAudio = async (text: string, id: number) => {
    // Stop any existing playback first
    stopCurrentAudio()

    setPlayingId(id)
    let voiceId = "en-US-ChristopherNeural" // Default US
    if (accent === "UK") voiceId = "en-GB-SoniaNeural"
    if (accent === "AU") voiceId = "en-AU-NatashaNeural"

    const url = `http://127.0.0.1:8000/tts?text=${text}&voice=${voiceId}`

    // Play logic
    const audio1 = new Audio(url)
    audioRef.current = audio1

    audio1.play().catch(e => console.error(e))

    // When first ends, wait and play second
    audio1.onended = () => {
      timeoutRef.current = setTimeout(() => {
        const audio2 = new Audio(url)
        audioRef.current = audio2
        audio2.play().catch(e => console.error(e))
        audio2.onended = () => {
          setPlayingId(null)
          // Clear ref if this specific audio finished
          if (audioRef.current === audio2) audioRef.current = null
        }
      }, 300)
    }
  }

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [newWord, setNewWord] = useState("")
  const [newMeaning, setNewMeaning] = useState("")
  const [addStatus, setAddStatus] = useState<"idle" | "validating" | "success" | "error" | "suggestion" | "confirm_needed">("idle")
  const [statusMessage, setStatusMessage] = useState("")
  const [suggestion, setSuggestion] = useState<any>(null)

  // AI Model Selection State
  const [modelType, setModelType] = useState<"exaone" | "solar-pro">("solar-pro")

  const [fetchError, setFetchError] = useState<string | null>(null)

  const fetchWords = async () => {
    try {
      setLoading(true)
      setFetchError(null)
      const res = await fetch("http://localhost:8000/words?limit=200")
      if (!res.ok) throw new Error("Server response not ok")
      const data = await res.json()
      setWords(data)
    } catch (e) {
      console.error("Failed to fetch words:", e)
      setFetchError("서버와 연결할 수 없습니다. 백엔드가 실행 중인지 확인해주세요.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchWords()
  }, [])

  // Add Word Logic
  const handleAddWord = async (confirmed = false, directWord?: string, directMeaning?: string) => {
    const targetWord = directWord || newWord
    const targetMeaning = directMeaning || newMeaning

    if (!targetWord) {
      alert("단어를 입력해주세요.")
      return
    }

    // 만약 뜻이 비어있으면 AI가 추천해준다는 것을 내부적으로 인지
    const isMeaningEmpty = !targetMeaning.trim()

    setAddStatus("validating")
    if (!confirmed) {
      setStatusMessage("AI 선생님이 단어를 꼼꼼히 검수하고 있습니다... 🤖")
    }

    try {
      const res = await fetch("http://127.0.0.1:8000/words", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          word: targetWord,
          meaning: targetMeaning,
          confirmed: confirmed,
          model_type: modelType
        }),
      })
      const data = await res.json()

      if (data.status === "SUCCESS") {
        setAddStatus("success")
        setStatusMessage(data.message)
        fetchWords()
        setTimeout(() => {
          setIsModalOpen(false)
          setAddStatus("idle")
          setNewWord("")
          setNewMeaning("")
        }, 1500)
      } else if (data.status === "CONFIRM_NEEDED") {
        setAddStatus("confirm_needed")
        setStatusMessage(data.message)
      } else if (data.status === "SUGGESTION") {
        setAddStatus("suggestion")
        setSuggestion(data.suggestion)
        setStatusMessage("잠깐! AI가 수정을 제안했습니다.")
      } else if (data.status === "DUPLICATE") {
        setAddStatus("error")
        setStatusMessage(data.message)
      } else {
        setAddStatus("error")
        setStatusMessage(data.message || "알 수 없는 오류가 발생했습니다.")
      }
    } catch (e) {
      setAddStatus("error")
      setStatusMessage("서버 연결 실패")
    }
  }

  // Chat Logic
  const handleSendMessage = async () => {
    if (!chatMessage.trim()) return

    const newMessage: ChatMessage = { role: "user", content: chatMessage }
    setChatHistory(prev => [...prev, newMessage])
    setChatMessage("")
    setIsChatLoading(true)

    try {
      const res = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: chatMessage,
          history: chatHistory
        }),
      })
      const data = await res.json()
      if (data.response) {
        setChatHistory(prev => [...prev, { role: "assistant", content: data.response }])
      }
    } catch (e) {
      console.error("Chat Error:", e)
      setChatHistory(prev => [...prev, { role: "assistant", content: "서버 연결에 실패했습니다. Solar Pro API 설정을 확인해주세요." }])
    } finally {
      setIsChatLoading(false)
    }
  }

  // Filter Logic
  const allFilteredWords = words.filter((w) =>
    w.word.toLowerCase().includes(search.toLowerCase()) ||
    w.meaning.includes(search)
  )

  // Pagination Logic
  const totalPages = Math.ceil(allFilteredWords.length / itemsPerPage)
  const filteredWords = allFilteredWords.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  )

  return (
    <main className="min-h-screen bg-slate-50 dark:bg-[#0d1117] transition-colors duration-300 font-sans selection:bg-indigo-100 selection:text-indigo-900 dark:selection:bg-indigo-900 dark:selection:text-indigo-100">
      <div className="max-w-3xl mx-auto px-6 py-12 space-y-8">

        {/* Header Section */}
        <div className="flex flex-col gap-6">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white transition-colors">TOEIC Whisper</h1>
              <p className="text-slate-500 mt-2 text-lg">Your Personal Vocabulary Coach</p>
            </div>

            {/* Study Mode Toggle Area */}
            <div className="flex flex-col gap-3 items-end">
              <div className="flex gap-4 items-center">
                {/* Accent Toggle */}
                <div className="bg-white border border-slate-200 dark:bg-[#161b22] dark:border-[#30363d] rounded-lg p-1 flex gap-1">
                  <button
                    onClick={() => setAccent("US")}
                    className={`px-2 py-1 text-xs font-bold rounded ${accent === "US" ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300" : "text-slate-400 hover:text-slate-600"}`}
                  >
                    🇺🇸 US
                  </button>
                  <button
                    onClick={() => setAccent("UK")}
                    className={`px-2 py-1 text-xs font-bold rounded ${accent === "UK" ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300" : "text-slate-400 hover:text-slate-600"}`}
                  >
                    🇬🇧 UK
                  </button>
                  <button
                    onClick={() => setAccent("AU")}
                    className={`px-2 py-1 text-xs font-bold rounded ${accent === "AU" ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300" : "text-slate-400 hover:text-slate-600"}`}
                  >
                    🇦🇺 AU
                  </button>
                </div>

                {/* Study Mode Toggle */}
                <div
                  onClick={() => setIsStudyMode(!isStudyMode)}
                  className={`cursor-pointer group flex items-center gap-3 px-4 py-2 rounded-full transition-all border ${isStudyMode
                    ? "bg-indigo-50 border-indigo-200 dark:bg-indigo-900/20 dark:border-indigo-500/50"
                    : "bg-white border-slate-200 dark:bg-[#161b22] dark:border-[#30363d] hover:border-indigo-200"
                    }`}
                >
                  <div className={`text-sm font-medium ${isStudyMode ? "text-indigo-700 dark:text-indigo-300" : "text-slate-500"}`}>
                    Study Mode
                  </div>
                  <div className={`w-10 h-6 rounded-full p-1 transition-colors relative ${isStudyMode ? "bg-indigo-600" : "bg-slate-300 dark:bg-slate-700"
                    }`}>
                    <div className={`w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${isStudyMode ? "translate-x-4" : "translate-x-0"
                      }`} />
                  </div>
                </div>

                {/* Dark Mode Toggle */}
                <div
                  onClick={() => setIsDarkMode(!isDarkMode)}
                  className={`cursor-pointer group flex items-center gap-3 px-4 py-2 rounded-full transition-all border ${isDarkMode
                    ? "bg-slate-800 border-slate-700"
                    : "bg-white border-slate-200 hover:border-indigo-200"
                    }`}
                >
                  <div className={`text-sm font-medium ${isDarkMode ? "text-slate-200" : "text-slate-500"}`}>
                    {isDarkMode ? "Dark" : "Light"}
                  </div>
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${isDarkMode ? "bg-slate-700 text-yellow-300" : "bg-orange-100 text-orange-500"
                    }`}>
                    {isDarkMode ? "🌙" : "☀️"}
                  </div>
                </div>

                {/* Items Per Page Select */}
                <select
                  value={itemsPerPage}
                  onChange={(e) => {
                    setItemsPerPage(Number(e.target.value))
                    setCurrentPage(1)
                  }}
                  className="h-10 bg-white dark:bg-[#161b22] border border-slate-200 dark:border-[#30363d] text-slate-700 dark:text-[#c9d1d9] text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block px-2.5 outline-none cursor-pointer hover:bg-slate-50 dark:hover:bg-[#21262d] transition-colors"
                >
                  <option value={10}>10 items</option>
                  <option value={30}>30 items</option>
                  <option value={50}>50 items</option>
                </select>
              </div>

              {/* LLM Chat Button */}
              <Button
                onClick={() => setIsChatOpen(!isChatOpen)}
                className={`h-10 px-5 rounded-full font-bold transition-all shadow-md ${isChatOpen
                  ? "bg-orange-500 hover:bg-orange-600 text-white"
                  : "bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-700 hover:to-indigo-600 text-white"
                  }`}
              >
                {isChatOpen ? "✕ Close Chat" : "✨ Talk with SOLAR LLM"}
              </Button>
            </div>
          </div>
        </div>

        {/* Chat Window Implementation */}
        {isChatOpen && (
          <div className="bg-white dark:bg-[#161b22] rounded-2xl border border-slate-200 dark:border-[#30363d] shadow-xl overflow-hidden animate-in fade-in slide-in-from-top-4 duration-300">
            <div className="p-4 border-b border-slate-100 dark:border-[#30363d] bg-slate-50/50 dark:bg-slate-800/30 flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className="text-xl">☀️</span>
                <span className="font-bold text-slate-700 dark:text-slate-200">Solar Pro Teacher</span>
              </div>
              <span className="text-[10px] bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400 px-2 py-1 rounded-full font-mono">POWERED BY UPSTAGE</span>
            </div>

            <div
              ref={chatScrollRef}
              className="h-[350px] overflow-y-auto p-4 space-y-4 scroll-smooth"
            >
              {chatHistory.length === 0 && (
                <div className="text-center py-10 text-slate-400 space-y-2">
                  <p>영어 학습이나 궁금한 점을 SOLAR AI에게 물어보세요!</p>
                  <p className="text-xs italic">"이 단어의 예문 좀 알려줘", "TOEIC Part 5 꿀팁 알려줘" 등</p>
                </div>
              )}
              {chatHistory.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm shadow-sm whitespace-pre-wrap ${msg.role === "user"
                    ? "bg-indigo-600 text-white rounded-tr-none"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-tl-none border border-slate-200 dark:border-slate-700"
                    }`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {isChatLoading && (
                <div className="flex justify-start">
                  <div className="bg-slate-100 dark:bg-slate-800 rounded-2xl px-4 py-2 text-sm text-slate-500 animate-pulse">
                    AI 선생님이 생각 중입니다...
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 bg-slate-50 dark:bg-slate-800/20 border-t border-slate-100 dark:border-[#30363d]">
              <div className="flex gap-2">
                <Input
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                  placeholder="메시지를 입력하세요..."
                  className="bg-white dark:bg-[#0d1117] border-slate-200 dark:border-[#30363d] dark:text-white"
                />
                <Button
                  onClick={handleSendMessage}
                  disabled={isChatLoading || !chatMessage.trim()}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white"
                >
                  Send
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Search and Add Section */}
        <div className="flex gap-3">
          <div className="relative flex-1">
            <span className="absolute left-3 top-3 text-slate-400">🔍</span>
            <Input
              placeholder="Search vocabulary..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 h-11 bg-white dark:bg-[#010409] border-slate-200 dark:border-[#30363d] focus:border-indigo-500 focus:ring-indigo-500/20 text-base dark:text-[#c9d1d9] transition-all shadow-sm"
            />
          </div>
          <Button
            onClick={() => setIsModalOpen(true)}
            className="h-11 px-6 bg-indigo-600 hover:bg-indigo-700 text-white font-medium shadow-sm hover:shadow-md transition-all"
          >
            + Add Word
          </Button>
        </div>

        {/* Content Section: Custom List */}
        <div className="space-y-3">
          {fetchError ? (
            <div className="text-center py-10 px-4 text-red-500 bg-red-50 dark:bg-red-900/10 rounded-xl border border-red-100 dark:border-red-900/30">
              <p className="font-bold text-lg mb-2">😢 데이터를 불러오지 못했습니다.</p>
              <p className="text-sm opacity-90">{fetchError}</p>
              <p className="text-xs mt-4 text-slate-500">터미널을 확인하거나 새로고침 해보세요.</p>
            </div>
          ) : loading ? (
            <div className="text-center py-20 text-slate-400 animate-pulse">
              Loading your collection...
            </div>
          ) : filteredWords.length > 0 ? (
            filteredWords.map((word) => (
              <div
                key={word.id}
                className="group bg-white dark:bg-[#161b22] rounded-xl border border-slate-100 dark:border-[#30363d] p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm hover:shadow-md hover:border-indigo-100 dark:hover:border-indigo-900 transition-all duration-200"
              >
                <div className="flex items-center gap-4">
                  <span className="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-300 flex items-center justify-center text-xs font-mono font-medium">
                    {word.id}
                  </span>

                  <button
                    onClick={() => playAudio(word.word, word.id)}
                    className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${playingId === word.id
                      ? "bg-indigo-600 text-white shadow-lg scale-110"
                      : "bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-slate-400 dark:text-slate-300 hover:text-indigo-600 hover:border-indigo-200 dark:hover:border-indigo-500"
                      }`}
                  >
                    {playingId === word.id ? "🔊" : "▶"}
                  </button>

                  <span
                    onDoubleClick={() => window.open(`https://dic.daum.net/search.do?q=${word.word}`, '_blank')}
                    className="text-xl font-bold text-slate-800 dark:text-slate-100 tracking-tight group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors cursor-pointer"
                    title="Double-click to search in dictionary"
                  >
                    {word.word}
                  </span>
                </div>

                <div className="flex items-center gap-4 pl-12 sm:pl-0">
                  <span
                    onClick={() => toggleReveal(word.id)}
                    className={
                      "text-lg text-slate-600 dark:text-slate-300 font-medium transition-all duration-300 " +
                      (isStudyMode ? "cursor-pointer select-none px-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800 " : "") +
                      (isStudyMode && !revealedIds.includes(word.id) ? "blur-md bg-slate-100 dark:bg-slate-800" : "")
                    }
                  >
                    {word.meaning}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="text-center py-20 text-slate-400 bg-white dark:bg-[#161b22] rounded-xl border border-dashed border-slate-200 dark:border-[#30363d]">
              No words found. Time to add some! ✍️
            </div>
          )}
        </div>

        {/* Pagination Controls */}
        {allFilteredWords.length > itemsPerPage && (
          <div className="flex justify-center items-center gap-4 pt-2 pb-8">
            <Button
              variant="outline"
              onClick={() => setCurrentPage(prev => (prev === 1 ? totalPages : prev - 1))}
              className="dark:bg-[#161b22] dark:border-[#30363d] dark:text-[#c9d1d9] dark:hover:bg-[#21262d]"
            >
              Previous
            </Button>
            <span className="text-sm font-medium text-slate-600 dark:text-[#8b949e]">
              Page {currentPage} of {totalPages}
            </span>
            <Button
              variant="outline"
              onClick={() => setCurrentPage(prev => (prev === totalPages ? 1 : prev + 1))}
              className="dark:bg-[#161b22] dark:border-[#30363d] dark:text-[#c9d1d9] dark:hover:bg-[#21262d]"
            >
              Next
            </Button>
          </div>
        )}
      </div>

      {/* Custom Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-[#161b22] rounded-2xl shadow-xl max-w-md w-full p-6 space-y-6 animate-in fade-in zoom-in duration-200 border border-slate-100 dark:border-[#30363d]">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Add New Word</h2>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">✕</button>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">English Word</label>
                <Input
                  placeholder="e.g. apple"
                  value={newWord}
                  onChange={(e) => setNewWord(e.target.value)}
                  className="h-11 bg-slate-50 dark:bg-[#010409] border-slate-200 dark:border-[#30363d] focus:bg-white dark:focus:bg-[#0d1117] transition-all text-lg dark:text-[#c9d1d9]"
                  autoFocus
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Korean Meaning</label>
                <Input
                  placeholder="비워두면 AI가 뜻을 추천해줍니다! ✨"
                  value={newMeaning}
                  onChange={(e) => setNewMeaning(e.target.value)}
                  className="h-11 bg-slate-50 dark:bg-[#010409] border-slate-200 dark:border-[#30363d] focus:bg-white dark:focus:bg-[#0d1117] transition-all text-lg dark:text-[#c9d1d9]"
                />
              </div>

              {/* Model Selection */}
              <div className="space-y-3 pt-2 border-t border-slate-100 dark:border-[#30363d]">
                <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Validator Model</label>
                <div className="grid grid-cols-2 gap-2">
                  <div
                    onClick={() => setModelType("exaone")}
                    className={
                      "cursor-pointer p-3 rounded-lg border text-sm font-medium transition-all text-center " +
                      (modelType === "exaone"
                        ? "bg-indigo-50 border-indigo-200 text-indigo-700 dark:bg-indigo-900/30 dark:border-indigo-500/50 dark:text-indigo-300"
                        : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100 dark:bg-[#010409] dark:border-[#30363d] dark:text-slate-400")
                    }
                  >
                    🤖 LG Exaone (Local)
                  </div>
                  <div
                    onClick={() => setModelType("solar-pro")}
                    className={
                      "cursor-pointer p-3 rounded-lg border text-sm font-medium transition-all text-center " +
                      (modelType === "solar-pro"
                        ? "bg-orange-50 border-orange-200 text-orange-700 dark:bg-orange-900/30 dark:border-orange-500/50 dark:text-orange-300"
                        : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100 dark:bg-[#010409] dark:border-[#30363d] dark:text-slate-400")
                    }
                  >
                    ☀️ Solar Pro (API)
                  </div>
                </div>

                {modelType === "solar-pro" && (
                  <p className="text-[10px] text-slate-400 mt-1 dark:text-slate-500 animate-in fade-in slide-in-from-top-2 duration-200">
                    * Using Server-side API Key for Solar Pro.
                  </p>
                )}
              </div>
            </div>

            {/* Enhanced Status Message */}
            {addStatus !== "idle" && (
              <div
                className={
                  "p-4 rounded-xl text-sm border " +
                  (addStatus === "validating"
                    ? "bg-indigo-50 border-indigo-100 text-indigo-700"
                    : addStatus === "success"
                      ? "bg-green-50 border-green-100 text-green-700"
                      : addStatus === "error"
                        ? "bg-red-50 border-red-100 text-red-700"
                        : "bg-amber-50 border-amber-100 text-amber-800")
                }
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-2 font-medium mb-1">
                      {addStatus === "validating" && <span className="animate-spin">⏳</span>}
                      {addStatus === "success" && <span>✅ Success</span>}
                      {addStatus === "error" && <span>🚨 Error</span>}
                      {addStatus === "suggestion" && <span>💡 AI Suggestion</span>}
                    </div>
                    <div className="pl-6 opacity-90 whitespace-pre-wrap">{statusMessage}</div>
                  </div>
                  {addStatus === "suggestion" && (
                    <button
                      onClick={() => handleAddWord(false)}
                      className="text-xs bg-white/50 hover:bg-white/80 border border-amber-200/50 rounded px-2 py-1 text-amber-700 transition w-fit whitespace-nowrap"
                      title="AI에게 다시 물어보기 (Re-verify)"
                    >
                      🔄 재검증
                    </button>
                  )}
                </div>

                {/* Suggestion UI */}
                {addStatus === "suggestion" && suggestion && (
                  <div className="mt-3 bg-white/50 rounded-lg p-3 text-xs border border-amber-200/50">
                    <div className="grid grid-cols-[60px_1fr] gap-1 mb-2">
                      <span className="text-blue-600 font-bold self-center">Input:</span>
                      <span className="font-bold text-sm text-blue-700 dark:text-blue-400">{newWord} : {newMeaning}</span>
                      <span className="text-green-600 font-bold">Fix:</span>
                      <span className="font-bold text-sm text-green-700 dark:text-green-400">
                        <span className={suggestion.corrected_word && suggestion.corrected_word !== newWord ? "text-red-600 dark:text-red-400" : ""}>
                          {suggestion.corrected_word || newWord}
                        </span>
                        {" : "}
                        <span className={suggestion.corrected_meaning && suggestion.corrected_meaning !== newMeaning ? "text-red-600 dark:text-red-400" : ""}>
                          {suggestion.corrected_meaning || newMeaning}
                        </span>
                      </span>
                    </div>
                    <div className="flex gap-2 mt-2">
                      {newMeaning.trim() !== "" && (
                        <Button
                          size="sm"
                          className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white border-0"
                          onClick={() => {
                            // 철자 검사 로직
                            const aiCorrectedWord = suggestion.corrected_word || newWord
                            if (newWord.trim().toLowerCase() !== aiCorrectedWord.trim().toLowerCase()) {
                              const alertMessage = [
                                "⚠️ 철자가 틀린 것 같아요!",
                                "",
                                "입력한 단어: " + newWord,
                                "올바른 철자: " + aiCorrectedWord,
                                "",
                                "철자를 수정해주세요.",
                              ].join("\n")
                              alert(alertMessage)
                              return
                            }

                            // 철자가 맞다면 내 입력 그대로 추가
                            handleAddWord(true, newWord, newMeaning)
                          }}
                        >
                          Use My Input
                        </Button>
                      )}

                      <Button
                        size="sm"
                        className="flex-1 bg-amber-600 hover:bg-amber-700 text-white border-0"
                        onClick={() => {
                          const finalWord = suggestion.corrected_word || newWord
                          const finalMeaning = suggestion.corrected_meaning || newMeaning

                          setNewWord(finalWord)
                          setNewMeaning(finalMeaning)

                          // 인자를 직접 넘겨서 바로 저장 호출 (비동기 상태 업데이트 문제 해결)
                          handleAddWord(true, finalWord, finalMeaning)
                        }}
                      >
                        Use AI Suggestion
                      </Button>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="w-full mt-2 border-slate-200 dark:border-slate-700 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                      onClick={() => {
                        setAddStatus("idle")
                        setStatusMessage("")
                        // Reset inputs on cancel if needed, or keep them as is (User said: "empty상태로 다시 단어입력받기전으로")
                        // "empty 상태" implies resetting or at least going back to edit mode.
                        // Assuming returning to 'idle' state allows editing again.
                      }}
                    >
                      Cancel & Edit
                    </Button>
                  </div>
                )}
                {/* Confirm UI */}
                {addStatus === "confirm_needed" && (
                  <div className="mt-3">
                    <Button
                      size="sm"
                      className="w-full bg-green-600 hover:bg-green-700 text-white border-0 font-bold"
                      onClick={() => handleAddWord(true)}
                    >
                      네, 추가할게요! (Confirm)
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="w-full mt-2 border-slate-200 dark:border-slate-700 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                      onClick={() => {
                        setAddStatus("idle")
                        setStatusMessage("")
                        // Reset to editing state (effectively canceling the confirmation step)
                      }}
                    >
                      취소 (Cancel)
                    </Button>
                  </div>
                )}
              </div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <Button variant="ghost" onClick={() => setIsModalOpen(false)} className="text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700">
                Cancel
              </Button>

              {/* Hide default confirm button if we are in suggestion/confirm state */}
              {addStatus !== "confirm_needed" && addStatus !== "suggestion" && (
                <Button
                  onClick={() => handleAddWord(false)}
                  disabled={addStatus === "validating"}
                  className="bg-slate-900 hover:bg-slate-800 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                >
                  {addStatus === "validating" ? "Checking..." : "Check & Add"}
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
