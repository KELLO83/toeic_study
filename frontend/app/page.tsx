"use client"

import { useEffect, useRef, useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

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

interface GameQuestion {
  instanceId: string
  wordId: number
  word: string
  meaning: string
  choices: string[]
  retryCount: number
}

interface GameResult {
  wordId: number
  word: string
  meaning: string
  attempts: number
  firstAttemptCorrect: boolean
  eventuallyCorrect: boolean
}

const shuffleArray = <T,>(items: T[]) => {
  const cloned = [...items]
  for (let index = cloned.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1))
    ;[cloned[index], cloned[swapIndex]] = [cloned[swapIndex], cloned[index]]
  }
  return cloned
}

const buildChoices = (pool: Word[], answerWordId: number, answerMeaning: string) => {
  const distractors = shuffleArray(
    pool.filter(
      (item) =>
        item.id !== answerWordId &&
        item.meaning.trim() &&
        item.meaning !== answerMeaning
    )
  )
    .slice(0, 3)
    .map((item) => item.meaning)

  return shuffleArray([answerMeaning, ...distractors])
}

const buildGameSet = (pool: Word[], questionCount: number) => {
  if (pool.length < 4) return []

  return shuffleArray(pool)
    .slice(0, questionCount)
    .map((item, index) => ({
      instanceId: `${item.id}-base-${index}`,
      wordId: item.id,
      word: item.word,
      meaning: item.meaning,
      choices: buildChoices(pool, item.id, item.meaning),
      retryCount: 0,
    }))
}

export default function Home() {
  const [words, setWords] = useState<Word[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")

  const [isStudyMode, setIsStudyMode] = useState(false)
  const [isDarkMode, setIsDarkMode] = useState(true)
  const [revealedIds, setRevealedIds] = useState<number[]>([])

  const [itemsPerPage, setItemsPerPage] = useState(10)
  const [currentPage, setCurrentPage] = useState(1)

  const [isChatOpen, setIsChatOpen] = useState(false)
  const [chatMessage, setChatMessage] = useState("")
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const [isChatLoading, setIsChatLoading] = useState(false)
  const chatScrollRef = useRef<HTMLDivElement>(null)

  const [accent, setAccent] = useState<"US" | "UK" | "AU">("US")
  const [playingId, setPlayingId] = useState<string | number | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [newWord, setNewWord] = useState("")
  const [newMeaning, setNewMeaning] = useState("")
  const [addStatus, setAddStatus] = useState<"idle" | "validating" | "success" | "error" | "suggestion" | "confirm_needed">("idle")
  const [statusMessage, setStatusMessage] = useState("")
  const [suggestion, setSuggestion] = useState<any>(null)
  const [modelType, setModelType] = useState<"exaone" | "solar-pro">("solar-pro")
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [fetchError, setFetchError] = useState<string | null>(null)

  const [viewMode, setViewMode] = useState<"list" | "game" | "result">("list")
  const [gameQuestions, setGameQuestions] = useState<GameQuestion[]>([])
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [selectedChoice, setSelectedChoice] = useState<string | null>(null)
  const [isAnswerLocked, setIsAnswerLocked] = useState(false)
  const [lastAnswerCorrect, setLastAnswerCorrect] = useState<boolean | null>(null)
  const [correctCount, setCorrectCount] = useState(0)
  const [gameResults, setGameResults] = useState<Record<number, GameResult>>({})

  const isDenseView = itemsPerPage === 15
  const isComfortView = itemsPerPage === 10
  const listHeightClass = isDenseView ? "h-[calc(100vh-205px)]" : "h-[calc(100vh-230px)]"

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
    }
  }, [chatHistory])

  useEffect(() => {
    if (isStudyMode) {
      setRevealedIds([])
    }
  }, [isStudyMode])

  useEffect(() => {
    const saved = localStorage.getItem("theme")
    if (saved === "light") setIsDarkMode(false)
  }, [])

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add("dark")
      localStorage.setItem("theme", "dark")
    } else {
      document.documentElement.classList.remove("dark")
      localStorage.setItem("theme", "light")
    }
  }, [isDarkMode])

  const toggleReveal = (id: number) => {
    if (!isStudyMode) return

    if (revealedIds.includes(id)) {
      setRevealedIds((prev) => prev.filter((item) => item !== id))
      return
    }

    setRevealedIds((prev) => [...prev, id])
  }

  const stopCurrentAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
  }

  const handleAudioPlayError = (error: unknown) => {
    if (error instanceof DOMException && error.name === "AbortError") {
      return
    }
    console.error(error)
  }

  const playAudio = async (text: string, id: string | number) => {
    stopCurrentAudio()

    setPlayingId(id)
    let voiceId = "en-US-ChristopherNeural"
    if (accent === "UK") voiceId = "en-GB-SoniaNeural"
    if (accent === "AU") voiceId = "en-AU-NatashaNeural"

    const url = `http://127.0.0.1:8000/tts?text=${text}&voice=${voiceId}`
    const audio1 = new Audio(url)
    audioRef.current = audio1
    audio1.play().catch(handleAudioPlayError)

    audio1.onended = () => {
      timeoutRef.current = setTimeout(() => {
        const audio2 = new Audio(url)
        audioRef.current = audio2
        audio2.play().catch(handleAudioPlayError)
        audio2.onended = () => {
          setPlayingId(null)
          if (audioRef.current === audio2) audioRef.current = null
        }
      }, 300)
    }
  }

  const fetchWords = async () => {
    try {
      setLoading(true)
      setFetchError(null)
      const response = await fetch("http://localhost:8000/words")
      if (!response.ok) throw new Error("Server response not ok")
      const data = await response.json()
      setWords(data)
    } catch (error) {
      console.error("Failed to fetch words:", error)
      setFetchError("서버와 연결할 수 없습니다. 백엔드가 실행 중인지 확인해주세요.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchWords()
  }, [])

  const allFilteredWords = words.filter(
    (item) =>
      item.word.toLowerCase().includes(search.toLowerCase()) ||
      item.meaning.includes(search)
  )

  const totalPages = Math.ceil(allFilteredWords.length / itemsPerPage)
  const filteredWords = allFilteredWords.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  )
  const currentQuestion = gameQuestions[currentQuestionIndex]
  const totalGameQuestions = gameQuestions.length
  const firstTryCorrectCount = Object.values(gameResults).filter((item) => item.firstAttemptCorrect).length
  const wrongResults = Object.values(gameResults).filter((item) => !item.firstAttemptCorrect)

  const resetGameState = () => {
    setGameQuestions([])
    setCurrentQuestionIndex(0)
    setSelectedChoice(null)
    setIsAnswerLocked(false)
    setLastAnswerCorrect(null)
    setCorrectCount(0)
    setGameResults({})
  }

  const exitGame = () => {
    resetGameState()
    setViewMode("list")
  }

  const startMiniGame = (sourceWords: Word[]) => {
    const eligibleWords = sourceWords.filter((item) => item.word.trim() && item.meaning.trim())
    if (eligibleWords.length < 4) {
      alert("미니게임을 시작하려면 뜻이 있는 단어가 최소 4개 필요합니다.")
      return
    }

    const nextQuestions = buildGameSet(eligibleWords, Math.min(10, eligibleWords.length))
    resetGameState()
    setGameQuestions(nextQuestions)
    setViewMode("game")
  }

  const restartWrongAnswers = () => {
    const wrongPool = wrongResults
      .map((item) => words.find((word) => word.id === item.wordId))
      .filter((item): item is Word => Boolean(item))

    if (wrongPool.length >= 4) {
      startMiniGame(wrongPool)
      return
    }

    startMiniGame(words)
  }

  const handleGameAnswer = (choice: string) => {
    if (!currentQuestion || isAnswerLocked) return

    const isCorrect = choice === currentQuestion.meaning
    const shouldRequeue = !isCorrect && currentQuestion.retryCount < 2
    const nextQuestionCount = gameQuestions.length + (shouldRequeue ? 1 : 0)
    setSelectedChoice(choice)
    setIsAnswerLocked(true)
    setLastAnswerCorrect(isCorrect)

    setGameResults((prev) => {
      const existing = prev[currentQuestion.wordId]
      return {
        ...prev,
        [currentQuestion.wordId]: {
          wordId: currentQuestion.wordId,
          word: currentQuestion.word,
          meaning: currentQuestion.meaning,
          attempts: (existing?.attempts ?? 0) + 1,
          firstAttemptCorrect: existing?.firstAttemptCorrect ?? isCorrect,
          eventuallyCorrect: isCorrect || existing?.eventuallyCorrect || false,
        },
      }
    })

    if (isCorrect) {
      setCorrectCount((prev) => prev + 1)
    } else if (shouldRequeue) {
      const retryQuestion: GameQuestion = {
        ...currentQuestion,
        instanceId: `${currentQuestion.wordId}-retry-${currentQuestion.retryCount + 1}-${Date.now()}`,
        choices: buildChoices(words, currentQuestion.wordId, currentQuestion.meaning),
        retryCount: currentQuestion.retryCount + 1,
      }

      setGameQuestions((prev) => {
        const insertAt = Math.min(prev.length, currentQuestionIndex + 3)
        const next = [...prev]
        next.splice(insertAt, 0, retryQuestion)
        return next
      })
    }

    window.setTimeout(() => {
      const nextIndex = currentQuestionIndex + 1
      setSelectedChoice(null)
      setIsAnswerLocked(false)
      setLastAnswerCorrect(null)

      if (nextIndex >= nextQuestionCount) {
        setViewMode("result")
        return
      }

      setCurrentQuestionIndex(nextIndex)
    }, 900)
  }

  const handleAddWord = async (confirmed = false, directWord?: string, directMeaning?: string) => {
    const targetWord = directWord || newWord
    const targetMeaning = directMeaning || newMeaning

    if (!targetWord) {
      alert("단어를 입력해주세요.")
      return
    }

    setAddStatus("validating")
    if (!confirmed) {
      setStatusMessage("AI 선생님이 단어를 꼼꼼히 검수하고 있습니다... 🤖")
    }

    try {
      const response = await fetch("http://127.0.0.1:8000/words", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          word: targetWord,
          meaning: targetMeaning,
          confirmed,
          model_type: modelType,
        }),
      })
      const data = await response.json()

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
    } catch (_error) {
      setAddStatus("error")
      setStatusMessage("서버 연결 실패")
    }
  }

  const handleExcelUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (!window.confirm("엑셀 파일을 업로드하면 기존 단어들이 모두 삭제되고 엑셀의 단어로 교체됩니다. 계속하시겠습니까?")) {
      event.target.value = ""
      return
    }

    setIsUploading(true)
    const formData = new FormData()
    formData.append("file", file)

    try {
      const response = await fetch("http://127.0.0.1:8000/words/upload", {
        method: "POST",
        body: formData,
      })
      const data = await response.json()

      if (response.ok && data.status === "SUCCESS") {
        await fetchWords()
        setCurrentPage(1)
        alert(data.message)
      } else {
        alert(`업로드 실패: ${data.detail || data.message || "알 수 없는 오류"}`)
      }
    } catch (error) {
      console.error("Upload Error:", error)
      alert("서버 연결 실패 또는 업로드 중 오류가 발생했습니다.")
    } finally {
      setIsUploading(false)
      event.target.value = ""
    }
  }

  const handleSendMessage = async () => {
    if (!chatMessage.trim()) return

    const newMessage: ChatMessage = { role: "user", content: chatMessage }
    setChatHistory((prev) => [...prev, newMessage])
    setChatMessage("")
    setIsChatLoading(true)

    try {
      const response = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: chatMessage,
          history: chatHistory,
        }),
      })
      const data = await response.json()
      if (data.response) {
        setChatHistory((prev) => [...prev, { role: "assistant", content: data.response }])
      }
    } catch (error) {
      console.error("Chat Error:", error)
      setChatHistory((prev) => [
        ...prev,
        { role: "assistant", content: "서버 연결에 실패했습니다. Solar Pro API 설정을 확인해주세요." },
      ])
    } finally {
      setIsChatLoading(false)
    }
  }

  useEffect(() => {
    const handlePageHotkeys = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const tagName = target?.tagName
      const isTypingTarget =
        tagName === "INPUT" ||
        tagName === "TEXTAREA" ||
        tagName === "SELECT" ||
        target?.isContentEditable

      if (isTypingTarget) return

      if (viewMode === "game" && currentQuestion) {
        if (["1", "2", "3", "4"].includes(event.key)) {
          event.preventDefault()
          const choice = currentQuestion.choices[Number(event.key) - 1]
          if (choice) handleGameAnswer(choice)
          return
        }

        if (event.key === "Escape") {
          event.preventDefault()
          exitGame()
          return
        }
      }

      if (viewMode !== "list" || totalPages <= 1) return

      if (event.key === "ArrowLeft") {
        event.preventDefault()
        setCurrentPage((prev) => (prev === 1 ? totalPages : prev - 1))
      }

      if (event.key === "ArrowRight") {
        event.preventDefault()
        setCurrentPage((prev) => (prev === totalPages ? 1 : prev + 1))
      }
    }

    window.addEventListener("keydown", handlePageHotkeys)
    return () => window.removeEventListener("keydown", handlePageHotkeys)
  }, [currentQuestion, totalPages, viewMode, isAnswerLocked, currentQuestionIndex, gameQuestions.length])

  useEffect(() => {
    if (viewMode !== "game" || !currentQuestion || isAnswerLocked) return

    playAudio(currentQuestion.word, `game-${currentQuestion.instanceId}`)
  }, [currentQuestion, viewMode])

  return (
    <main className="min-h-screen bg-slate-50 font-sans transition-colors duration-300 selection:bg-indigo-100 selection:text-indigo-900 dark:bg-[#0d1117] dark:selection:bg-indigo-900 dark:selection:text-indigo-100">
      <div className={`mx-auto px-4 ${isDenseView ? "max-w-6xl space-y-2 py-2.5" : "max-w-5xl space-y-3 py-3"}`}>
        <div className={`flex flex-col ${isDenseView ? "gap-1" : "gap-2"}`}>
          <div className={`flex flex-col ${isDenseView ? "gap-1" : "gap-2"} xl:flex-row xl:items-start xl:justify-between`}>
            <div>
              <h1 className={`${isDenseView ? "text-2xl" : "text-[30px]"} font-extrabold tracking-tight text-slate-900 transition-colors dark:text-white`}>
                TOEIC Whisper
              </h1>
              <p className={`mt-0.5 text-slate-500 ${isDenseView ? "text-[11px]" : "text-xs"}`}>
                Your Personal Vocabulary Coach
              </p>
            </div>

            <div className={`flex flex-col gap-1 xl:items-end`}>
              <div className="flex flex-wrap items-center gap-2 xl:justify-end">
                <div className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1 dark:border-[#30363d] dark:bg-[#161b22]">
                  <button
                    onClick={() => setAccent("US")}
                    className={`rounded px-2 py-1 text-xs font-bold ${accent === "US" ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300" : "text-slate-400 hover:text-slate-600"}`}
                  >
                    🇺🇸 US
                  </button>
                  <button
                    onClick={() => setAccent("UK")}
                    className={`rounded px-2 py-1 text-xs font-bold ${accent === "UK" ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300" : "text-slate-400 hover:text-slate-600"}`}
                  >
                    🇬🇧 UK
                  </button>
                  <button
                    onClick={() => setAccent("AU")}
                    className={`rounded px-2 py-1 text-xs font-bold ${accent === "AU" ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300" : "text-slate-400 hover:text-slate-600"}`}
                  >
                    🇦🇺 AU
                  </button>
                </div>

                <div
                  onClick={() => setIsStudyMode(!isStudyMode)}
                  className={`group flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 transition-all ${
                    isStudyMode
                      ? "border-indigo-200 bg-indigo-50 dark:border-indigo-500/50 dark:bg-indigo-900/20"
                      : "border-slate-200 bg-white hover:border-indigo-200 dark:border-[#30363d] dark:bg-[#161b22]"
                  }`}
                >
                  <div className={`text-sm font-medium ${isStudyMode ? "text-indigo-700 dark:text-indigo-300" : "text-slate-500"}`}>
                    Study Mode
                  </div>
                  <div className={`relative h-6 w-10 rounded-full p-1 transition-colors ${isStudyMode ? "bg-indigo-600" : "bg-slate-300 dark:bg-slate-700"}`}>
                    <div className={`h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${isStudyMode ? "translate-x-4" : "translate-x-0"}`} />
                  </div>
                </div>

                <div
                  onClick={() => setIsDarkMode(!isDarkMode)}
                  className={`group flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 transition-all ${
                    isDarkMode ? "border-slate-700 bg-slate-800" : "border-slate-200 bg-white hover:border-indigo-200"
                  }`}
                >
                  <div className={`text-sm font-medium ${isDarkMode ? "text-slate-200" : "text-slate-500"}`}>
                    {isDarkMode ? "Dark" : "Light"}
                  </div>
                  <div className={`flex h-6 w-6 items-center justify-center rounded-full transition-colors ${isDarkMode ? "bg-slate-700 text-yellow-300" : "bg-orange-100 text-orange-500"}`}>
                    {isDarkMode ? "🌙" : "☀️"}
                  </div>
                </div>

                <div className="inline-flex items-center rounded-lg border border-slate-200 bg-white p-1 shadow-sm dark:border-[#30363d] dark:bg-[#161b22]">
                  {[10, 15].map((count) => {
                    const isActive = itemsPerPage === count

                    return (
                      <button
                        key={count}
                        type="button"
                        onClick={() => {
                          setItemsPerPage(count)
                          setCurrentPage(1)
                        }}
                        className={`${isDenseView ? "h-8 px-2.5 text-[11px]" : "h-9 px-3 text-xs"} rounded-md font-semibold transition-all ${
                          isActive
                            ? "bg-indigo-600 text-white shadow-sm"
                            : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-[#21262d]"
                        }`}
                      >
                        {count} items
                      </button>
                    )
                  })}
                </div>
              </div>

              <Button
                onClick={() => setIsChatOpen(!isChatOpen)}
                className={`${isDenseView ? "h-8 px-3 text-[11px]" : "h-8.5 px-4 text-xs"} rounded-full font-bold shadow-md transition-all ${
                  isChatOpen
                    ? "bg-orange-500 text-white hover:bg-orange-600"
                    : "bg-gradient-to-r from-indigo-600 to-indigo-500 text-white hover:from-indigo-700 hover:to-indigo-600"
                }`}
              >
                {isChatOpen ? "✕ Close Chat" : "✨ Talk with SOLAR LLM"}
              </Button>
            </div>
          </div>
        </div>

        {isChatOpen && (
          <div className="animate-in slide-in-from-top-4 fade-in overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl duration-300 dark:border-[#30363d] dark:bg-[#161b22]">
            <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/50 p-4 dark:border-[#30363d] dark:bg-slate-800/30">
              <div className="flex items-center gap-2">
                <span className="text-xl">☀️</span>
                <span className="font-bold text-slate-700 dark:text-slate-200">Solar Pro Teacher</span>
              </div>
              <span className="rounded-full bg-indigo-100 px-2 py-1 font-mono text-[10px] text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400">
                POWERED BY UPSTAGE
              </span>
            </div>

            <div ref={chatScrollRef} className="h-[350px] space-y-4 overflow-y-auto p-4 scroll-smooth">
              {chatHistory.length === 0 && (
                <div className="space-y-2 py-10 text-center text-slate-400">
                  <p>영어 학습이나 궁금한 점을 SOLAR AI에게 물어보세요!</p>
                  <p className="text-xs italic">"이 단어의 예문 좀 알려줘", "TOEIC Part 5 꿀팁 알려줘" 등</p>
                </div>
              )}
              {chatHistory.map((message, index) => (
                <div key={index} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm shadow-sm ${
                      message.role === "user"
                        ? "rounded-tr-none bg-indigo-600 text-white"
                        : "rounded-tl-none border border-slate-200 bg-slate-100 text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                    }`}
                  >
                    {message.content}
                  </div>
                </div>
              ))}
              {isChatLoading && (
                <div className="flex justify-start">
                  <div className="animate-pulse rounded-2xl bg-slate-100 px-4 py-2 text-sm text-slate-500 dark:bg-slate-800">
                    AI 선생님이 생각 중입니다...
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-slate-100 bg-slate-50 p-4 dark:border-[#30363d] dark:bg-slate-800/20">
              <div className="flex gap-2">
                <Input
                  value={chatMessage}
                  onChange={(event) => setChatMessage(event.target.value)}
                  onKeyDown={(event) => event.key === "Enter" && handleSendMessage()}
                  placeholder="메시지를 입력하세요..."
                  className="border-slate-200 bg-white dark:border-[#30363d] dark:bg-[#0d1117] dark:text-white"
                />
                <Button
                  onClick={handleSendMessage}
                  disabled={isChatLoading || !chatMessage.trim()}
                  className="bg-indigo-600 text-white hover:bg-indigo-700"
                >
                  Send
                </Button>
              </div>
            </div>
          </div>
        )}

        {viewMode === "list" && (
          <>
            <div className={`flex flex-wrap ${isDenseView ? "gap-1.5" : "gap-2"}`}>
              <div className="relative flex-1">
                <span className={`absolute left-3 text-slate-400 ${isDenseView ? "top-2" : "top-2.5"}`}>🔍</span>
                <Input
                  placeholder="Search vocabulary..."
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  className={`pl-10 ${isDenseView ? "h-9 text-xs" : "h-10 text-sm"} border-slate-200 bg-white shadow-sm transition-all focus:border-indigo-500 focus:ring-indigo-500/20 dark:border-[#30363d] dark:bg-[#010409] dark:text-[#c9d1d9]`}
                />
              </div>
              <Button
                onClick={() => setIsModalOpen(true)}
                className={`${isDenseView ? "h-9 px-3 text-xs" : "h-9.5 px-4 text-sm"} bg-indigo-600 text-white shadow-sm transition-all hover:bg-indigo-700 hover:shadow-md`}
              >
                + Add Word
              </Button>
              <Button
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className={`${isDenseView ? "h-9 px-3 text-xs" : "h-9.5 px-4 text-sm"} bg-orange-600 text-white shadow-sm transition-all hover:bg-orange-700 hover:shadow-md`}
                title="Upload Excel"
              >
                {isUploading ? "⏳ Uploading..." : "📤 Upload"}
              </Button>
              <input
                type="file"
                accept=".xlsx, .xls"
                className="hidden"
                ref={fileInputRef}
                onChange={handleExcelUpload}
              />
              <Button
                onClick={() => window.open("http://localhost:8000/words/export", "_blank")}
                className={`${isDenseView ? "h-9 px-3 text-xs" : "h-9.5 px-4 text-sm"} bg-green-600 text-white shadow-sm transition-all hover:bg-green-700 hover:shadow-md`}
                title="Export to Excel"
              >
                📥 Excel
              </Button>
              <Button
                onClick={() => startMiniGame(allFilteredWords.length >= 4 ? allFilteredWords : words)}
                className={`${isDenseView ? "h-9 px-3 text-xs" : "h-9.5 px-4 text-sm"} bg-slate-900 text-white shadow-sm transition-all hover:bg-slate-800 hover:shadow-md dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200`}
              >
                🎮 Mini Game
              </Button>
            </div>
          </>
        )}

        <div className="space-y-1">
          {viewMode === "game" && currentQuestion ? (
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-[#30363d] dark:bg-[#161b22]">
              <div className="flex flex-col gap-3 border-b border-slate-100 pb-4 dark:border-[#30363d] sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-500 dark:text-indigo-300">Mini Game Session</p>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                    Question {currentQuestionIndex + 1} / {totalGameQuestions}
                  </h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">숫자키 `1-4`로도 답할 수 있습니다.</p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    Correct {correctCount}
                  </div>
                  <Button
                    variant="outline"
                    onClick={exitGame}
                    className="h-9 rounded-full dark:border-[#30363d] dark:bg-[#161b22] dark:text-[#c9d1d9] dark:hover:bg-[#21262d]"
                  >
                    Exit
                  </Button>
                </div>
              </div>

              <div className="mt-5 space-y-5">
                <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                  <div
                    className="h-full rounded-full bg-indigo-500 transition-all duration-300"
                    style={{ width: `${((currentQuestionIndex + 1) / totalGameQuestions) * 100}%` }}
                  />
                </div>

                <Card className="border-slate-200 shadow-none dark:border-[#30363d] dark:bg-[#0d1117]">
                  <CardContent className="flex flex-col items-center gap-4 px-4 py-8 text-center sm:px-6">
                    <div className="space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">
                        Listen and Recall
                      </p>
                      <h3 className="text-4xl font-black tracking-tight text-slate-900 dark:text-white sm:text-5xl">
                        {currentQuestion.word}
                      </h3>
                    </div>
                    <Button
                      onClick={() => playAudio(currentQuestion.word, `game-${currentQuestion.instanceId}`)}
                      className="h-11 rounded-full bg-indigo-600 px-5 text-sm font-bold text-white hover:bg-indigo-700"
                    >
                      🔊 발음 듣기
                    </Button>
                  </CardContent>
                </Card>

                <div className="grid gap-3 sm:grid-cols-2">
                  {currentQuestion.choices.map((choice, index) => {
                    const isCorrectChoice = choice === currentQuestion.meaning
                    const isSelectedChoice = selectedChoice === choice
                    const showCorrect = isAnswerLocked && isCorrectChoice
                    const showWrong = isAnswerLocked && isSelectedChoice && !isCorrectChoice

                    return (
                      <button
                        key={`${currentQuestion.instanceId}-${choice}`}
                        onClick={() => handleGameAnswer(choice)}
                        disabled={isAnswerLocked}
                        className={`min-h-24 rounded-2xl border px-4 py-4 text-left text-sm font-semibold transition-all ${
                          showCorrect
                            ? "border-emerald-400 bg-emerald-50 text-emerald-700 dark:border-emerald-500 dark:bg-emerald-900/20 dark:text-emerald-300"
                            : showWrong
                              ? "border-rose-400 bg-rose-50 text-rose-700 dark:border-rose-500 dark:bg-rose-900/20 dark:text-rose-300"
                              : "border-slate-200 bg-white text-slate-700 hover:border-indigo-300 hover:bg-indigo-50 dark:border-[#30363d] dark:bg-[#0d1117] dark:text-slate-200 dark:hover:border-indigo-500 dark:hover:bg-indigo-950/30"
                        }`}
                      >
                        <span className="mb-2 block text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">
                          Choice {index + 1}
                        </span>
                        <span className="block text-base leading-6">{choice}</span>
                      </button>
                    )
                  })}
                </div>

                <div
                  className={`rounded-2xl border px-4 py-3 text-sm ${
                    lastAnswerCorrect === true
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/20 dark:text-emerald-300"
                      : lastAnswerCorrect === false
                        ? "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/20 dark:text-rose-300"
                        : "border-slate-200 bg-slate-50 text-slate-500 dark:border-[#30363d] dark:bg-[#0d1117] dark:text-slate-400"
                  }`}
                >
                  {lastAnswerCorrect === true && `정답입니다. "${currentQuestion.word}" = "${currentQuestion.meaning}"`}
                  {lastAnswerCorrect === false && `오답입니다. 정답은 "${currentQuestion.meaning}" 입니다. 같은 단어가 뒤에서 다시 나옵니다.`}
                  {lastAnswerCorrect === null && "단어를 보고 가장 알맞은 뜻을 골라보세요."}

                  {lastAnswerCorrect === false && (
                    <div className="mt-3 rounded-xl border border-rose-200 bg-white/70 px-3 py-2 dark:border-rose-900/60 dark:bg-[#0d1117]">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-rose-500 dark:text-rose-300">
                        Wrong Word
                      </p>
                      <p className="mt-1 text-base font-bold text-slate-900 dark:text-white">{currentQuestion.word}</p>
                      <p className="text-sm text-slate-600 dark:text-slate-300">{currentQuestion.meaning}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : viewMode === "result" ? (
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-[#30363d] dark:bg-[#161b22]">
              <div className="space-y-2 text-center">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-500 dark:text-indigo-300">Session Complete</p>
                <h2 className="text-3xl font-black tracking-tight text-slate-900 dark:text-white">미니게임 결과</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  첫 시도 기준 정답 {firstTryCorrectCount}개, 오답 {wrongResults.length}개
                </p>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl bg-slate-50 px-4 py-4 text-center dark:bg-[#0d1117]">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">Score</p>
                  <p className="mt-2 text-3xl font-black text-slate-900 dark:text-white">
                    {totalGameQuestions > 0 ? Math.round((firstTryCorrectCount / totalGameQuestions) * 100) : 0}%
                  </p>
                </div>
                <div className="rounded-2xl bg-slate-50 px-4 py-4 text-center dark:bg-[#0d1117]">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">Correct</p>
                  <p className="mt-2 text-3xl font-black text-emerald-600 dark:text-emerald-300">{firstTryCorrectCount}</p>
                </div>
                <div className="rounded-2xl bg-slate-50 px-4 py-4 text-center dark:bg-[#0d1117]">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">Wrong</p>
                  <p className="mt-2 text-3xl font-black text-rose-600 dark:text-rose-300">{wrongResults.length}</p>
                </div>
              </div>

              <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-[#30363d] dark:bg-[#0d1117]">
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">틀린 단어</h3>
                <div className="mt-3 space-y-2">
                  {wrongResults.length > 0 ? (
                    wrongResults.map((item) => (
                      <div
                        key={`wrong-${item.wordId}`}
                        className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-[#30363d] dark:bg-[#161b22]"
                      >
                        <div>
                          <p className="font-bold text-slate-900 dark:text-white">{item.word}</p>
                          <p className="text-slate-500 dark:text-slate-400">{item.meaning}</p>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          <span className="rounded-full bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 dark:bg-rose-950/30 dark:text-rose-300">
                            first try wrong
                          </span>
                          <span className="text-[11px] text-slate-400 dark:text-slate-500">
                            {item.attempts} tries
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-slate-500 dark:text-slate-400">모든 단어를 맞혔습니다.</p>
                  )}
                </div>
              </div>

              <div className="mt-5 flex flex-wrap justify-center gap-2">
                <Button
                  onClick={restartWrongAnswers}
                  className="h-10 rounded-full bg-indigo-600 px-5 text-sm font-bold text-white hover:bg-indigo-700"
                >
                  Retry Wrong Answers
                </Button>
                <Button
                  variant="outline"
                  onClick={() => startMiniGame(words)}
                  className="h-10 rounded-full dark:border-[#30363d] dark:bg-[#161b22] dark:text-[#c9d1d9] dark:hover:bg-[#21262d]"
                >
                  New 10-Word Set
                </Button>
                <Button
                  variant="outline"
                  onClick={exitGame}
                  className="h-10 rounded-full dark:border-[#30363d] dark:bg-[#161b22] dark:text-[#c9d1d9] dark:hover:bg-[#21262d]"
                >
                  Back to List
                </Button>
              </div>
            </div>
          ) : fetchError ? (
            <div className="rounded-xl border border-red-100 bg-red-50 px-4 py-10 text-center text-red-500 dark:border-red-900/30 dark:bg-red-900/10">
              <p className="mb-2 text-lg font-bold">😢 데이터를 불러오지 못했습니다.</p>
              <p className="text-sm opacity-90">{fetchError}</p>
              <p className="mt-4 text-xs text-slate-500">터미널을 확인하거나 새로고침 해보세요.</p>
            </div>
          ) : loading ? (
            <div className="animate-pulse py-20 text-center text-slate-400">Loading your collection...</div>
          ) : filteredWords.length > 0 ? (
            <div
              className={`${listHeightClass} overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-[#30363d] dark:bg-[#161b22]`}
              style={{
                display: "grid",
                gridTemplateRows: `repeat(${filteredWords.length}, minmax(0, 1fr))`,
              }}
            >
              {filteredWords.map((word) => (
                <div
                  key={word.id}
                  className={`group grid min-h-0 items-center border-b border-slate-100 last:border-b-0 dark:border-[#30363d] ${
                    isDenseView
                      ? "grid-cols-[34px_30px_minmax(96px,156px)_minmax(0,1fr)] gap-1.5 px-2.5 py-1.5"
                      : "grid-cols-[40px_36px_minmax(136px,210px)_minmax(0,1fr)] gap-2 px-3 py-2 sm:gap-3"
                  }`}
                >
                  <span className={`${isDenseView ? "h-6 w-6 text-[10px]" : "h-8 w-8 text-[11px]"} flex items-center justify-center rounded-full bg-slate-100 font-mono font-medium text-slate-500 dark:bg-slate-700 dark:text-slate-300`}>
                    {word.id}
                  </span>

                  <button
                    onClick={() => playAudio(word.word, word.id)}
                    className={`${isDenseView ? "h-7 w-7 text-xs" : "h-8 w-8 text-sm"} flex items-center justify-center rounded-full transition-all ${
                      playingId === word.id
                        ? "bg-indigo-600 text-white shadow"
                        : "border border-slate-200 bg-white text-slate-400 hover:border-indigo-200 hover:text-indigo-600 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:hover:border-indigo-500"
                    }`}
                  >
                    {playingId === word.id ? "🔊" : "▶"}
                  </button>

                  <span
                    onDoubleClick={() => window.open(`https://dic.daum.net/search.do?q=${word.word}`, "_blank")}
                    className={`${isDenseView ? "text-[13px]" : isComfortView ? "text-[18px] sm:text-[19px]" : "text-[15px] sm:text-base"} cursor-pointer truncate font-bold tracking-tight text-slate-800 transition-colors group-hover:text-indigo-600 dark:text-slate-100 dark:group-hover:text-indigo-400`}
                    title="Double-click to search in dictionary"
                  >
                    {word.word}
                  </span>

                  <span
                    onClick={() => toggleReveal(word.id)}
                    className={
                      `${isDenseView ? "text-[13px] leading-4 truncate" : isComfortView ? "text-[17px] leading-6" : "text-[15px] leading-5"} text-slate-600 transition-all duration-300 dark:text-slate-300 ` +
                      (isStudyMode ? `${isDenseView ? "cursor-pointer select-none rounded px-1 py-0.5" : "cursor-pointer select-none rounded px-1.5 py-0.5"} hover:bg-slate-100 dark:hover:bg-slate-800 ` : "") +
                      (isStudyMode && !revealedIds.includes(word.id) ? "blur-md bg-slate-100 dark:bg-slate-800" : "")
                    }
                    title={word.meaning}
                  >
                    {word.meaning}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 bg-white py-20 text-center text-slate-400 dark:border-[#30363d] dark:bg-[#161b22]">
              No words found. Time to add some! ✍️
            </div>
          )}
        </div>

        {viewMode === "list" && allFilteredWords.length > itemsPerPage && (
          <div className={`flex items-center justify-center ${isDenseView ? "gap-3 pb-1 pt-0.5" : "gap-4 pb-1 pt-0.5"}`}>
            <Button
              variant="outline"
              onClick={() => setCurrentPage((prev) => (prev === 1 ? totalPages : prev - 1))}
              className={`${isDenseView ? "h-8 px-3 text-xs" : ""} dark:border-[#30363d] dark:bg-[#161b22] dark:text-[#c9d1d9] dark:hover:bg-[#21262d]`}
            >
              Previous
            </Button>
            <span className={`${isDenseView ? "text-xs" : "text-sm"} font-medium text-slate-600 dark:text-[#8b949e]`}>
              Page {currentPage} of {totalPages}
            </span>
            <Button
              variant="outline"
              onClick={() => setCurrentPage((prev) => (prev === totalPages ? 1 : prev + 1))}
              className={`${isDenseView ? "h-8 px-3 text-xs" : ""} dark:border-[#30363d] dark:bg-[#161b22] dark:text-[#c9d1d9] dark:hover:bg-[#21262d]`}
            >
              Next
            </Button>
          </div>
        )}
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm">
          <div className="animate-in zoom-in fade-in w-full max-w-md space-y-6 rounded-2xl border border-slate-100 bg-white p-6 shadow-xl duration-200 dark:border-[#30363d] dark:bg-[#161b22]">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Add New Word</h2>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">English Word</label>
                <Input
                  placeholder="e.g. apple"
                  value={newWord}
                  onChange={(event) => setNewWord(event.target.value)}
                  className="h-11 border-slate-200 bg-slate-50 text-lg transition-all focus:bg-white dark:border-[#30363d] dark:bg-[#010409] dark:text-[#c9d1d9] dark:focus:bg-[#0d1117]"
                  autoFocus
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Korean Meaning</label>
                <Input
                  placeholder="비워두면 AI가 뜻을 추천해줍니다! ✨"
                  value={newMeaning}
                  onChange={(event) => setNewMeaning(event.target.value)}
                  className="h-11 border-slate-200 bg-slate-50 text-lg transition-all focus:bg-white dark:border-[#30363d] dark:bg-[#010409] dark:text-[#c9d1d9] dark:focus:bg-[#0d1117]"
                />
              </div>

              <div className="space-y-3 border-t border-slate-100 pt-2 dark:border-[#30363d]">
                <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Validator Model</label>
                <div className="grid grid-cols-2 gap-2">
                  <div
                    onClick={() => setModelType("exaone")}
                    className={
                      "cursor-pointer rounded-lg border p-3 text-center text-sm font-medium transition-all " +
                      (modelType === "exaone"
                        ? "border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-500/50 dark:bg-indigo-900/30 dark:text-indigo-300"
                        : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 dark:border-[#30363d] dark:bg-[#010409] dark:text-slate-400")
                    }
                  >
                    🤖 LG Exaone (Local)
                  </div>
                  <div
                    onClick={() => setModelType("solar-pro")}
                    className={
                      "cursor-pointer rounded-lg border p-3 text-center text-sm font-medium transition-all " +
                      (modelType === "solar-pro"
                        ? "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-500/50 dark:bg-orange-900/30 dark:text-orange-300"
                        : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 dark:border-[#30363d] dark:bg-[#010409] dark:text-slate-400")
                    }
                  >
                    ☀️ Nemotron (API)
                  </div>
                </div>

                {modelType === "solar-pro" && (
                  <p className="animate-in slide-in-from-top-2 fade-in mt-1 text-[10px] text-slate-400 duration-200 dark:text-slate-500">
                    * Using Server-side API Key for Nemotron.
                  </p>
                )}
              </div>
            </div>

            {addStatus !== "idle" && (
              <div
                className={
                  "rounded-xl border p-4 text-sm " +
                  (addStatus === "validating"
                    ? "border-indigo-100 bg-indigo-50 text-indigo-700"
                    : addStatus === "success"
                      ? "border-green-100 bg-green-50 text-green-700"
                      : addStatus === "error"
                        ? "border-red-100 bg-red-50 text-red-700"
                        : "border-amber-100 bg-amber-50 text-amber-800")
                }
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="mb-1 flex items-center gap-2 font-medium">
                      {addStatus === "validating" && <span className="animate-spin">⏳</span>}
                      {addStatus === "success" && <span>✅ Success</span>}
                      {addStatus === "error" && <span>🚨 Error</span>}
                      {addStatus === "suggestion" && <span>💡 AI Suggestion</span>}
                    </div>
                    <div className="whitespace-pre-wrap pl-6 opacity-90">{statusMessage}</div>
                  </div>
                  {addStatus === "suggestion" && (
                    <button
                      onClick={() => handleAddWord(false)}
                      className="w-fit whitespace-nowrap rounded border border-amber-200/50 bg-white/50 px-2 py-1 text-xs text-amber-700 transition hover:bg-white/80"
                      title="AI에게 다시 물어보기 (Re-verify)"
                    >
                      🔄 재검증
                    </button>
                  )}
                </div>

                {addStatus === "suggestion" && suggestion && (
                  <div className="mt-3 rounded-lg border border-amber-200/50 bg-white/50 p-3 text-xs">
                    <div className="mb-2 grid grid-cols-[60px_1fr] gap-1">
                      <span className="self-center font-bold text-blue-600">Input:</span>
                      <span className="text-sm font-bold text-blue-700 dark:text-blue-400">
                        {newWord} : {newMeaning}
                      </span>
                      <span className="font-bold text-green-600">Fix:</span>
                      <span className="text-sm font-bold text-green-700 dark:text-green-400">
                        <span className={suggestion.corrected_word && suggestion.corrected_word !== newWord ? "text-red-600 dark:text-red-400" : ""}>
                          {suggestion.corrected_word || newWord}
                        </span>
                        {" : "}
                        <span className={suggestion.corrected_meaning && suggestion.corrected_meaning !== newMeaning ? "text-red-600 dark:text-red-400" : ""}>
                          {suggestion.corrected_meaning || newMeaning}
                        </span>
                      </span>
                    </div>
                    <div className="mt-2 flex gap-2">
                      {newMeaning.trim() !== "" && (
                        <Button
                          size="sm"
                          className="flex-1 border-0 bg-indigo-600 text-white hover:bg-indigo-700"
                          onClick={() => {
                            const aiCorrectedWord = suggestion.corrected_word || newWord
                            if (newWord.trim().toLowerCase() !== aiCorrectedWord.trim().toLowerCase()) {
                              alert(["⚠️ 철자가 틀린 것 같아요!", "", `입력한 단어: ${newWord}`, `올바른 철자: ${aiCorrectedWord}`, "", "철자를 수정해주세요."].join("\n"))
                              return
                            }
                            handleAddWord(true, newWord, newMeaning)
                          }}
                        >
                          Use My Input
                        </Button>
                      )}

                      <Button
                        size="sm"
                        className="flex-1 border-0 bg-amber-600 text-white hover:bg-amber-700"
                        onClick={() => {
                          const finalWord = suggestion.corrected_word || newWord
                          const finalMeaning = suggestion.corrected_meaning || newMeaning
                          setNewWord(finalWord)
                          setNewMeaning(finalMeaning)
                          handleAddWord(true, finalWord, finalMeaning)
                        }}
                      >
                        Use AI Suggestion
                      </Button>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2 w-full border-slate-200 text-slate-500 hover:text-slate-700 dark:border-slate-700 dark:hover:text-slate-300"
                      onClick={() => {
                        setAddStatus("idle")
                        setStatusMessage("")
                      }}
                    >
                      Cancel & Edit
                    </Button>
                  </div>
                )}

                {addStatus === "confirm_needed" && (
                  <div className="mt-3">
                    <Button
                      size="sm"
                      className="w-full border-0 bg-green-600 font-bold text-white hover:bg-green-700"
                      onClick={() => handleAddWord(true)}
                    >
                      네, 추가할게요! (Confirm)
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2 w-full border-slate-200 text-slate-500 hover:text-slate-700 dark:border-slate-700 dark:hover:text-slate-300"
                      onClick={() => {
                        setAddStatus("idle")
                        setStatusMessage("")
                      }}
                    >
                      취소 (Cancel)
                    </Button>
                  </div>
                )}
              </div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="ghost"
                onClick={() => setIsModalOpen(false)}
                className="text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
              >
                Cancel
              </Button>

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
