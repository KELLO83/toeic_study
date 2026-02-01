"use client"

import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Headphones, Upload, FileAudio, Play, Pause, ChevronRight, CheckCircle2, AlertCircle, Loader2, Trash2 } from "lucide-react"

interface AudioFile {
    id: number
    filename: string
    status: "processing" | "completed" | "error"
    upload_date: string
    progress?: number
}

interface Transcript {
    start_time: number
    end_time: number
    text: string
    label?: string
}

interface Question {
    id: number
    question_number: number
    part: number
    set_number?: number
    start_time: number
    end_time: number
    transcripts: Transcript[]
}

export default function LCPage() {
    const [files, setFiles] = useState<AudioFile[]>([])
    const [selectedFile, setSelectedFile] = useState<AudioFile | null>(null)
    const [lcData, setLcData] = useState<Question[]>([])
    const [loading, setLoading] = useState(false)
    const [uploading, setUploading] = useState(false)
    const [activeQuestionId, setActiveQuestionId] = useState<number | null>(null)

    const [activePart, setActivePart] = useState<number | "all">("all")

    const audioRef = useRef<HTMLAudioElement>(null)
    const checkTimeRef = useRef<(() => void) | null>(null) // Track current checkTime listener
    const [isPlaying, setIsPlaying] = useState(false)
    const [currentTime, setCurrentTime] = useState(0)
    const [playingSegment, setPlayingSegment] = useState<{ start: number, end: number } | null>(null) // Track currently playing segment
    const [isAudioLoading, setIsAudioLoading] = useState(false) // Loading state for playback


    // Load Dark Mode from localStorage (Synced with Word page)
    useEffect(() => {
        const saved = localStorage.getItem("theme")
        if (saved === "light") {
            document.documentElement.classList.remove("dark")
        } else {
            // Default: Dark mode
            document.documentElement.classList.add("dark")
            if (!saved) localStorage.setItem("theme", "dark")
        }
    }, [])



    // Fetch file list on mount
    useEffect(() => {
        fetchFiles()
    }, [])

    // Dynamic polling: faster when processing
    useEffect(() => {
        const hasProcessing = files.some(f => f.status === "processing")
        const interval = setInterval(fetchFiles, hasProcessing ? 1000 : 5000)
        return () => clearInterval(interval)
    }, [files])

    const fetchFiles = async () => {
        try {
            const res = await fetch("http://localhost:8000/lc/files")
            const data = await res.json()
            setFiles(data)
        } catch (e) {
            console.error("Failed to fetch files:", e)
        }
    }

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.[0]) return
        setUploading(true)
        const formData = new FormData()
        formData.append("file", e.target.files[0])
        try {
            const res = await fetch("http://localhost:8000/lc/upload", { method: "POST", body: formData })
            if (res.ok) fetchFiles()
        } catch (e) { console.error("Upload failed:", e) }
        finally { setUploading(false) }
    }

    const selectFile = async (file: AudioFile) => {
        if (file.status !== "completed") return
        setSelectedFile(file)
        setLoading(true)
        setActivePart("all") // Reset part filter
        try {
            const res = await fetch(`http://localhost:8000/lc/data/${file.id}`)
            const data = await res.json()
            setLcData(data)
        } catch (e) { console.error("Failed to fetch LC data:", e) }
        finally { setLoading(false) }
    }

    const playSegment = async (start: number, end: number, questionId: number | null = null) => {
        console.log(`playSegment called: start=${start}, end=${end}, questionId=${questionId}`)

        if (!audioRef.current) {
            console.error("audioRef.current is null!")
            return
        }

        const audio = audioRef.current

        // Clean up previous playback
        audio.pause()
        if (checkTimeRef.current) {
            audio.removeEventListener("timeupdate", checkTimeRef.current)
            checkTimeRef.current = null
            console.log("Previous listener cleaned up")
        }

        // Only set active question if a valid questionId is provided
        if (questionId !== null) {
            setActiveQuestionId(questionId)
        }
        setIsAudioLoading(true) // Show loading state


        // Create new checkTime function
        const checkTime = () => {
            if (audioRef.current && audioRef.current.currentTime >= end) {
                audioRef.current.removeEventListener("timeupdate", checkTime)
                audioRef.current.pause()
                setIsPlaying(false)
                // Keep playingSegment to maintain highlight after playback ends
                checkTimeRef.current = null
                console.log("Playback stopped at end time")
            }
        }


        checkTimeRef.current = checkTime

        const playAfterSeek = async () => {
            try {
                audio.currentTime = start
                console.log(`Seeking to ${start}s, audio duration: ${audio.duration}s`)

                await audio.play()
                setIsPlaying(true)
                setPlayingSegment({ start, end }) // Set currently playing segment
                setIsAudioLoading(false) // Hide loading state
                console.log("Playback started")

                // Register end-time listener AFTER play succeeds
                audio.addEventListener("timeupdate", checkTime)

            } catch (err) {
                console.error("Playback failed:", err)
                setIsAudioLoading(false)
                setPlayingSegment(null)
            }
        }


        // If audio is ready, play immediately
        if (audio.readyState >= 3) {
            await playAfterSeek()
        } else {
            console.log("Waiting for audio to load...")
            audio.addEventListener('canplaythrough', playAfterSeek, { once: true })
            audio.load()
        }
    }


    const filteredData = activePart === "all"
        ? lcData
        : lcData.filter(q => q.part === activePart)


    const deleteFile = async (e: React.MouseEvent, fileId: number) => {
        e.stopPropagation() // Prevent card click
        if (!confirm("정말 이 파일을 삭제하시겠습니까?")) return

        try {
            const res = await fetch(`http://localhost:8000/lc/files/${fileId}`, {
                method: "DELETE"
            })
            if (res.ok) {
                setFiles(files.filter(f => f.id !== fileId))
                if (selectedFile?.id === fileId) {
                    setSelectedFile(null)
                    setLcData([])
                    setActiveQuestionId(null)
                }
            } else if (res.status === 404) {
                // Already deleted or not found
                alert("이미 삭제된 파일이거나 존재하지 않는 파일입니다. 목록에서 제거합니다.")
                setFiles(files.filter(f => f.id !== fileId))
                if (selectedFile?.id === fileId) {
                    setSelectedFile(null)
                    setLcData([])
                    setActiveQuestionId(null)
                }
            } else {
                const errData = await res.json()
                alert(`파일 삭제 실패: ${errData.detail || "알 수 없는 오류"}`)
            }
        } catch (err) {
            console.error(err)
            alert("파일 삭제 요청 중 네트워크 오류 발생")
        }
    }

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 p-2 md:p-4 space-y-4 animate-in fade-in duration-700 w-full mx-auto">
            {/* Hidden Audio Player */}
            {selectedFile && (
                <audio
                    ref={audioRef}
                    src={`http://localhost:8000/lc/audio/${selectedFile.id}`}
                    preload="auto"
                    onTimeUpdate={() => {
                        // Only update currentTime when actually playing
                        if (audioRef.current && !audioRef.current.paused) {
                            setCurrentTime(audioRef.current.currentTime)
                        }
                    }}
                    onEnded={() => {
                        setIsPlaying(false)
                        setCurrentTime(-1) // Reset highlighting
                    }}
                    className="hidden"
                />
            )}



            {/* Header Section */}

            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-4xl font-black bg-gradient-to-r from-indigo-500 to-purple-600 bg-clip-text text-transparent flex items-center gap-3">
                        <Headphones className="w-10 h-10 text-indigo-500" />
                        TOEIC LC Trainer
                        {isAudioLoading && (
                            <span className="ml-3 flex items-center gap-2 text-base font-medium text-indigo-500">
                                <Loader2 className="w-5 h-5 animate-spin" />
                                <span className="animate-pulse">로딩 중...</span>
                            </span>
                        )}
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 mt-2 text-lg">
                        AI Whisper로 파싱된 대본으로 듣기 실력을 향상시키세요.
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    <label className="cursor-pointer group">
                        <div className="flex items-center gap-2 px-6 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm hover:shadow-md hover:border-indigo-500 transition-all group-active:scale-95 transition-all">
                            {uploading ? <Loader2 className="w-5 h-5 animate-spin text-indigo-500" /> : <Upload className="w-5 h-5 text-indigo-500 group-hover:scale-110 transition-transform" />}
                            <span className="font-bold text-slate-700 dark:text-slate-200">{uploading ? "업로드 중..." : "음원 업로드"}</span>
                        </div>
                        <Input type="file" className="hidden" accept="audio/*" onChange={handleFileUpload} disabled={uploading} />
                    </label>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
                {/* Sidebar: Audio List */}
                <div className="lg:col-span-1 space-y-4">
                    <h2 className="text-xl font-bold text-slate-800 dark:text-slate-200 px-2 flex items-center gap-2">
                        <FileAudio className="w-5 h-5 text-purple-500" />
                        파일 목록
                    </h2>
                    <div className="space-y-3 overflow-y-auto max-h-[70vh] pr-2 custom-scrollbar">
                        {files.length === 0 && !uploading && (
                            <div className="text-center py-10 text-slate-400 bg-white/50 dark:bg-slate-900/50 rounded-3xl border border-dashed border-slate-200 dark:border-slate-800">
                                음원을 업로드하세요.
                            </div>
                        )}
                        {files.map((file) => (
                            <Card
                                key={file.id}
                                className={`cursor-pointer border-0 shadow-sm transition-all hover:scale-[1.02] group/card relative ${selectedFile?.id === file.id ? "ring-2 ring-indigo-500 bg-indigo-50/50 dark:bg-indigo-900/20" : "bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm"
                                    }`}
                                onClick={() => selectFile(file)}
                            >
                                <CardContent className="p-4 flex items-center gap-3">
                                    <div className={`p-3 rounded-2xl ${file.status === "completed" ? "bg-green-100 dark:bg-green-900/30 text-green-600" :
                                        file.status === "error" ? "bg-red-100 dark:bg-red-900/30 text-red-600" : "bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600"
                                        }`}>
                                        {file.status === "completed" ? <CheckCircle2 className="w-5 h-5" /> : file.status === "error" ? <AlertCircle className="w-5 h-5" /> : <Loader2 className="w-5 h-5 animate-spin" />}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="font-bold text-slate-700 dark:text-slate-200 truncate pr-6">{file.filename}</p>
                                        <div className="flex items-center gap-2 mt-1">
                                            <p className="text-xs text-slate-400">{new Date(file.upload_date).toLocaleDateString()}</p>
                                            {file.status === "processing" && (
                                                <div className="flex-1 flex items-center gap-2 ml-2">
                                                    <Progress value={file.progress || 0} className="h-1.5" />
                                                    <span className="text-[10px] font-bold text-indigo-500 min-w-[24px]">{file.progress || 0}%</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                    {/* Delete Button */}
                                    <button
                                        className="absolute top-2 right-2 p-1.5 rounded-full text-slate-400 hover:bg-red-100 hover:text-red-500 opacity-0 group-hover/card:opacity-100 transition-all z-10"
                                        onClick={(e) => deleteFile(e, file.id)}
                                        title="Delete File"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>

                {/* Main: Transcript Viewer ... */}
                <div className="lg:col-span-3">
                    {selectedFile ? (
                        <Card className="bg-white/90 dark:bg-slate-900/90 backdrop-blur-xl border-slate-200 dark:border-slate-800 shadow-2xl rounded-[2.5rem] overflow-hidden">
                            <CardHeader className="border-b border-slate-100 dark:border-slate-800 p-8 flex flex-col gap-6">
                                <div className="flex flex-row items-center justify-between">
                                    <div>
                                        <CardTitle className="text-2xl font-black text-slate-800 dark:text-slate-100">{selectedFile.filename}</CardTitle>
                                        <p className="text-slate-500 mt-1 uppercase tracking-wider text-xs font-bold">Transcription Details</p>
                                    </div>
                                    {selectedFile && (
                                        <audio
                                            ref={audioRef}
                                            src={`http://localhost:8000/lc/audio/${selectedFile.id}`}
                                            onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                                            onPlay={() => setIsPlaying(true)}
                                            onPause={() => setIsPlaying(false)}
                                            className="hidden"
                                        />
                                    )}
                                </div>

                                {/* Part Filter Tabs */}
                                {!loading && lcData.length > 0 && (
                                    <div className="flex flex-col gap-4 p-4 bg-slate-50 dark:bg-slate-900/50 rounded-2xl border border-slate-100 dark:border-slate-800">
                                        {/* Part Filter */}
                                        <div className="flex gap-2 p-1 bg-white dark:bg-slate-800 rounded-xl w-fit shadow-sm border border-slate-100 dark:border-slate-700">
                                            {["all", 1, 2, 3, 4].map((part) => (
                                                <button
                                                    key={part}
                                                    onClick={() => setActivePart(part as any)}
                                                    className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${activePart === part
                                                        ? "bg-indigo-500 text-white shadow-md shadow-indigo-500/30"
                                                        : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
                                                        }`}
                                                >
                                                    {part === "all" ? "Whole" : `Part ${part}`}
                                                </button>
                                            ))}
                                        </div>

                                        {/* Question Navigator */}
                                        <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto pr-2 custom-scrollbar">
                                            {filteredData.map((q) => (
                                                <button
                                                    key={q.id}
                                                    onClick={() => {
                                                        const el = document.getElementById(`question-${q.id}`);
                                                        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                                        setActiveQuestionId(q.id);
                                                    }}
                                                    className={`w-10 h-10 rounded-xl text-xs font-bold transition-all border-2 
                                                        ${activeQuestionId === q.id
                                                            ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300"
                                                            : "border-transparent bg-white dark:bg-slate-800 text-slate-500 hover:border-indigo-200 dark:hover:border-slate-700"
                                                        } ${q.set_number ? "ring-1 ring-purple-200" : ""}`}
                                                    title={q.set_number ? `Part of Set ${q.set_number}` : `Question ${q.question_number}`}
                                                >
                                                    {q.question_number}
                                                </button>
                                            ))}
                                            {filteredData.length === 0 && <span className="text-xs text-slate-400 p-2">No questions available.</span>}
                                        </div>
                                    </div>
                                )}
                            </CardHeader>

                            <CardContent className="p-0 h-[60vh] flex flex-col">
                                {loading ? (
                                    <div className="flex-1 flex flex-col items-center justify-center gap-4">
                                        <div className="relative">
                                            <Loader2 className="w-12 h-12 text-indigo-500 animate-spin" />
                                            <div className="absolute inset-0 blur-xl bg-indigo-500/30 animate-pulse"></div>
                                        </div>
                                        <p className="text-slate-500 font-medium animate-pulse">데이터를 불러오는 중...</p>
                                    </div>
                                ) : (
                                    <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-12 custom-scrollbar">
                                        {/* Grouping Logic Render */}
                                        {(() => {
                                            // Group questions by set_number
                                            const grouped: { type: 'set' | 'single', setNum?: number, questions: Question[] }[] = [];
                                            const processedSets = new Set<number>();

                                            filteredData.forEach(q => {
                                                if (q.set_number) {
                                                    if (!processedSets.has(q.set_number)) {
                                                        const setQuestions = filteredData.filter(fq => fq.set_number === q.set_number);
                                                        processedSets.add(q.set_number);
                                                        grouped.push({ type: 'set', setNum: q.set_number, questions: setQuestions });
                                                    }
                                                } else {
                                                    grouped.push({ type: 'single', questions: [q] });
                                                }
                                            });

                                            if (grouped.length === 0 && lcData.length > 0) {
                                                return <div className="text-center py-20 text-slate-400 italic">선택한 Part에 해당하는 문제가 없습니다.</div>;
                                            }
                                            if (lcData.length === 0) {
                                                return <div className="text-center py-20 text-slate-400 italic">추출된 문제 정보가 없습니다.</div>;
                                            }

                                            return grouped.map((group, gIdx) => (
                                                <div key={gIdx} className="space-y-6">
                                                    {group.type === 'set' ? (
                                                        <div className="bg-white dark:bg-slate-900/50 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
                                                            {/* Set Header / Conversation Script */}
                                                            <div className="mb-8 p-6 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-700">
                                                                <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4">Conversation (Questions {group.questions[0].question_number}-{group.questions[group.questions.length - 1].question_number})</h3>
                                                                <div className="space-y-4">
                                                                    {/* Show conversation transcripts from the first question (deduplicated) */}
                                                                    {group.questions[0].transcripts
                                                                        .filter(t => t.label === 'conversation' || !t.label)
                                                                        .map((t, tIdx) => (
                                                                            <p
                                                                                key={tIdx}
                                                                                className={`text-lg leading-relaxed cursor-pointer transition-colors ${playingSegment && t.start_time === playingSegment.start && t.end_time === playingSegment.end
                                                                                    ? "text-indigo-600 dark:text-indigo-400 font-bold"
                                                                                    : "text-slate-700 dark:text-slate-300 hover:text-indigo-500"
                                                                                    }`}

                                                                                onClick={() => playSegment(t.start_time, t.end_time, null)}
                                                                            >
                                                                                {t.text}
                                                                            </p>
                                                                        ))}
                                                                </div>
                                                            </div>

                                                            {/* Questions in Set */}
                                                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                                                {group.questions.map(q => {
                                                                    const questionTranscripts = q.transcripts.filter(t => t.label === 'question');
                                                                    // Combine all question transcripts into one
                                                                    const combinedQuestionText = questionTranscripts.map(t => t.text).join(' ');
                                                                    // Get full time range (first start to last end)
                                                                    const questionStartTime = questionTranscripts.length > 0 ? questionTranscripts[0].start_time : 0;
                                                                    const questionEndTime = questionTranscripts.length > 0 ? questionTranscripts[questionTranscripts.length - 1].end_time : 0;

                                                                    return (
                                                                        <div key={q.id} id={`question-${q.id}`} className={`p-4 rounded-2xl border transition-all scroll-mt-32 ${activeQuestionId === q.id ? "border-indigo-500 bg-indigo-50/50" : "border-slate-100 dark:border-slate-800"}`}>
                                                                            <div className="flex items-center gap-3 mb-3">
                                                                                <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 font-bold text-sm">
                                                                                    {q.question_number}
                                                                                </span>
                                                                                {questionTranscripts.length > 0 && (
                                                                                    <Button
                                                                                        variant="ghost"
                                                                                        size="sm"
                                                                                        className="h-8 w-8 p-0 rounded-full"
                                                                                        onClick={() => playSegment(questionStartTime, questionEndTime, q.id)}
                                                                                    >
                                                                                        <Play className="w-4 h-4 text-slate-500 hover:text-indigo-500" />
                                                                                    </Button>
                                                                                )}
                                                                            </div>
                                                                            <div className="space-y-2">
                                                                                {/* Question Text - Combined and Clickable */}
                                                                                {combinedQuestionText ? (
                                                                                    <p
                                                                                        className="text-md font-medium text-slate-800 dark:text-slate-200 cursor-pointer hover:text-indigo-600 transition-colors"
                                                                                        onClick={() => playSegment(questionStartTime, questionEndTime, q.id)}
                                                                                    >
                                                                                        {combinedQuestionText}
                                                                                    </p>
                                                                                ) : (
                                                                                    <p className="text-sm text-slate-400 italic">질문 텍스트 없음</p>
                                                                                )}
                                                                            </div>
                                                                        </div>
                                                                    )
                                                                })}

                                                            </div>
                                                        </div>
                                                    ) : (
                                                        // Single Question (Part 1, 2 style)
                                                        <div key={group.questions[0].id} id={`question-${group.questions[0].id}`} className="group animate-in slide-in-from-bottom-4 duration-500 scroll-mt-32">
                                                            <div className="flex items-start gap-6">
                                                                <Button
                                                                    variant="ghost"
                                                                    className={`w-14 h-14 rounded-2xl flex flex-col items-center justify-center gap-1 transition-all ${activeQuestionId === group.questions[0].id
                                                                        ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/40 translate-x-1"
                                                                        : "bg-slate-100 dark:bg-slate-800 text-slate-500 hover:bg-indigo-50 hover:text-indigo-600 dark:hover:bg-indigo-900/30"
                                                                        }`}
                                                                    onClick={() => playSegment(group.questions[0].start_time, group.questions[0].end_time, group.questions[0].id)}
                                                                >
                                                                    <span className="text-[10px] font-bold opacity-70">Q.</span>
                                                                    <span className="text-lg font-black">{group.questions[0].question_number}</span>
                                                                </Button>

                                                                <div className="flex-1 space-y-3">
                                                                    {group.questions[0].transcripts.map((t, idx) => (
                                                                        <p
                                                                            key={idx}
                                                                            className={`text-lg leading-relaxed cursor-pointer p-4 rounded-3xl transition-all border-2 border-transparent hover:border-indigo-100 dark:hover:border-indigo-900/30 hover:bg-white dark:hover:bg-slate-800/50 ${currentTime >= t.start_time && currentTime <= t.end_time
                                                                                ? "text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50/50 dark:bg-indigo-900/10 border-indigo-200 dark:border-indigo-900/40 shadow-sm"
                                                                                : "text-slate-600 dark:text-slate-300"
                                                                                }`}
                                                                            onClick={() => playSegment(t.start_time, t.end_time, group.questions[0].id)}
                                                                        >
                                                                            {t.text}
                                                                        </p>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            ));
                                        })()}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="h-[75vh] flex flex-col items-center justify-center text-center p-10 bg-white/40 dark:bg-slate-900/40 backdrop-blur-md rounded-[3rem] border border-slate-200/50 dark:border-slate-800/50">
                            <div className="w-24 h-24 bg-indigo-100 dark:bg-indigo-900/30 rounded-full flex items-center justify-center mb-6 animate-bounce">
                                <FileAudio className="w-12 h-12 text-indigo-500" />
                            </div>
                            <h3 className="text-2xl font-bold text-slate-800 dark:text-slate-200">음원을 선택해 주세요</h3>
                            <p className="text-slate-500 mt-2 max-w-md">왼쪽 목록에서 완성된 음원을 클릭하거나 새 파일을 업로드하여 대본을 확인해 보세요.</p>
                        </div>
                    )}
                </div>
            </div>

            <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
        .dark .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; }
      `}</style>
        </div>
    )
}
