import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { complaintAPI } from '../services/api';
import { Send, MapPin, Globe, Loader2, CheckCircle2, Image, ExternalLink, Mic, MicOff, AlertTriangle, Check, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { imageVerificationClass, imageVerificationLabel } from '../utils/imageVerification';

const PRIORITY_COLORS = {
  1: 'bg-green-100 text-green-700',
  2: 'bg-blue-100 text-blue-700',
  3: 'bg-yellow-100 text-yellow-700',
  4: 'bg-orange-100 text-orange-700',
  5: 'bg-red-100 text-red-700',
};
const PRIORITY_LABELS = { 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Urgent', 5: 'Critical' };

function mapsUrl(lat, lon) {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
}

export default function SubmitComplaint() {
  const [text, setText] = useState('');
  const [language, setLanguage] = useState('');
  const [image, setImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceSource, setVoiceSource] = useState('');
  const [voiceDraft, setVoiceDraft] = useState(null);

  const fileRef = useRef();
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const navigate = useNavigate();

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const appendVoiceText = (value, source) => {
    const cleanText = value.trim();
    if (!cleanText) return;
    setText((prev) => (prev ? `${prev.trim()} ${cleanText}` : cleanText));
    setLanguage('en');
    setVoiceSource(source || 'auto');
  };

  const useVoiceDraft = () => {
    if (!voiceDraft?.text) return;
    appendVoiceText(voiceDraft.text, voiceDraft.source);
    setVoiceDraft(null);
    toast.success('Voice text added. Please check it once before submitting.');
  };

  const toggleMic = async () => {
    if (isRecording) {
      // Stop → triggers onstop which sends to Whisper
      mediaRecorderRef.current?.stop();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];
      setVoiceDraft(null);

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        // Kill mic stream
        stream.getTracks().forEach((t) => t.stop());
        setIsRecording(false);
        setIsTranscribing(true);

        try {
          const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          const { data } = await complaintAPI.transcribe(blob, language, true);
          const englishText = data.english_text || data.text;
          if (englishText) {
            const source = data.detected_language || language || 'auto';
            if (data.review_required) {
              setVoiceDraft({
                text: englishText,
                source,
                warnings: data.warnings || [],
                confidence: data.confidence,
                model: data.model,
              });
              setVoiceSource('');
              toast.error('Voice translation looks unreliable. Review it before using.');
            } else {
              appendVoiceText(englishText, source);
              setVoiceDraft(null);
              toast.success(data.translated ? 'Voice translated to English!' : 'Voice transcribed!');
            }
          } else {
            toast.error('No speech detected — try again.');
          }
        } catch {
          toast.error('Voice translation failed. Is the backend running?');
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
    } catch (err) {
      toast.error('Microphone access denied. Please allow mic access and try again.');
    }
  };

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setImage(file);
    setImagePreview(URL.createObjectURL(file));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;

    // Stop recording if active before submitting
    if (isRecording) mediaRecorderRef.current?.stop();

    setLoading(true);
    setResult(null);

    try {
      const payload = { text: text.trim() };
      if (language) payload.language = language;

      if (navigator.geolocation) {
        try {
          const pos = await new Promise((resolve, reject) =>
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
          );
          payload.latitude = pos.coords.latitude;
          payload.longitude = pos.coords.longitude;
        } catch {
          // Location not available, that's fine
        }
      }

      const { data } = await complaintAPI.submit(payload);

      if (image && data.tickets?.length > 0) {
        try {
          const { data: updated } = await complaintAPI.uploadImage(data.tickets[0].id, image);
          data.tickets[0] = updated;
        } catch {
          toast.error('Complaint filed but image upload failed');
        }
      }

      setResult(data);
      toast.success(`${data.total_complaints_detected} complaint(s) registered!`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to submit complaint');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-slate-800 mb-2">Report a Civic Issue</h1>
      <p className="text-slate-500 mb-8">
        Describe your problem in any language — type or speak. Our AI will classify it
        and route it to the right department.
      </p>

      {!result ? (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Language selector */}
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1.5">
              <Globe className="w-4 h-4 inline mr-1" />
              Language (optional — we auto-detect)
            </label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition text-sm"
            >
              <option value="">Auto-detect</option>
              <option value="en">English</option>
              <option value="kn">ಕನ್ನಡ (Kannada)</option>
              <option value="hi">हिन्दी (Hindi)</option>
            </select>
          </div>

          {/* Complaint text with mic button */}
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1.5">
              Describe your complaint
            </label>
            <div className="relative">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={6}
                placeholder={
                  isRecording
                    ? 'Listening… speak now'
                    : 'Type your complaint, or tap the mic to speak in English, Hindi, or Kannada.'
                }
                className={`w-full px-4 py-3 pr-14 rounded-lg border transition text-sm resize-none outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 ${
                  isRecording ? 'border-red-400 bg-red-50' : 'border-slate-300'
                }`}
                required
                minLength={5}
              />

              {/* Mic button — bottom-right of textarea */}
              <button
                type="button"
                onClick={toggleMic}
                disabled={isTranscribing}
                title={isRecording ? 'Stop recording' : 'Speak your complaint'}
                className={`absolute bottom-3 right-3 p-2 rounded-full transition ${
                  isRecording
                    ? 'bg-red-500 text-white animate-pulse shadow-lg shadow-red-200'
                    : isTranscribing
                    ? 'bg-brand-400 text-white animate-spin'
                    : 'bg-slate-100 text-slate-500 hover:bg-brand-100 hover:text-brand-600'
                }`}
              >
                {isTranscribing
                  ? <Loader2 className="w-5 h-5" />
                  : isRecording
                  ? <MicOff className="w-5 h-5" />
                  : <Mic className="w-5 h-5" />}
              </button>
            </div>

            {isRecording && (
              <p className="text-xs text-red-500 mt-1 flex items-center gap-1">
                <span className="inline-block w-2 h-2 rounded-full bg-red-500 animate-ping" />
                Recording… tap mic to stop
              </p>
            )}
            {isTranscribing && (
              <p className="text-xs text-brand-500 mt-1 flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" />
                Whisper is translating your audio to English...
              </p>
            )}
            {voiceSource && !isRecording && !isTranscribing && (
              <p className="text-xs text-green-600 mt-1">
                Last voice input translated to English from {voiceSource}.
              </p>
            )}
            {voiceDraft && !isRecording && !isTranscribing && (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-amber-800">
                      Translation needs review
                    </p>
                    <p className="mt-1 text-sm text-amber-900">{voiceDraft.text}</p>
                    {voiceDraft.warnings?.length > 0 && (
                      <p className="mt-1 text-xs text-amber-700">
                        {voiceDraft.warnings[0]}
                      </p>
                    )}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={useVoiceDraft}
                        className="inline-flex items-center gap-1.5 rounded-md bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700"
                      >
                        <Check className="h-3.5 w-3.5" />
                        Use text
                      </button>
                      <button
                        type="button"
                        onClick={() => setVoiceDraft(null)}
                        className="inline-flex items-center gap-1.5 rounded-md border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100"
                      >
                        <X className="h-3.5 w-3.5" />
                        Discard
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
            {!isRecording && !isTranscribing && (
              <p className="text-xs text-slate-400 mt-1">
                Tip: You can mention multiple issues in one message. We'll create separate tickets for each.
              </p>
            )}
          </div>

          {/* Image upload */}
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1.5">
              <Image className="w-4 h-4 inline mr-1" />
              Attach a photo (optional)
            </label>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              onChange={handleImageChange}
              className="hidden"
            />
            {imagePreview ? (
              <div className="relative inline-block">
                <img src={imagePreview} alt="Preview" className="h-32 rounded-lg border border-slate-200 object-cover" />
                <button
                  type="button"
                  onClick={() => { setImage(null); setImagePreview(null); fileRef.current.value = ''; }}
                  className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 text-xs flex items-center justify-center"
                >×</button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => fileRef.current.click()}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-dashed border-slate-300 text-slate-500 text-sm hover:border-brand-400 hover:text-brand-600 transition"
              >
                <Image className="w-4 h-4" />
                Click to upload a photo
              </button>
            )}
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading || !text.trim()}
            className="w-full py-3 bg-brand-600 hover:bg-brand-700 text-white rounded-lg font-medium transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                AI is analyzing your complaint...
              </>
            ) : (
              <>
                <Send className="w-5 h-5" />
                Submit Complaint
              </>
            )}
          </button>
        </form>
      ) : (
        <div className="space-y-6">
          <div className="bg-green-50 border border-green-200 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-3">
              <CheckCircle2 className="w-6 h-6 text-green-600" />
              <h2 className="text-lg font-semibold text-green-800">{result.message}</h2>
            </div>
            {result.localized_message && (
              <p className="text-sm text-green-700 mb-2">{result.localized_message}</p>
            )}
            <p className="text-sm text-green-600">
              We detected {result.total_complaints_detected} complaint(s) in your message.
            </p>
          </div>

          {result.tickets?.map((ticket) => (
            <div key={ticket.ticket_id} className="bg-white border border-slate-200 rounded-xl p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <p className="text-xs font-mono text-slate-400">{ticket.ticket_id}</p>
                  <h3 className="text-lg font-semibold text-slate-700 mt-1">{ticket.description}</h3>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${PRIORITY_COLORS[ticket.priority]}`}>
                  {PRIORITY_LABELS[ticket.priority]}
                </span>
              </div>

              {ticket.image_url && (
                <div className="mb-4">
                  <img src={ticket.image_url} alt="Complaint" className="w-full max-h-48 object-cover rounded-lg border border-slate-100" />
                  <span className={`inline-flex mt-2 px-2 py-1 rounded text-xs font-medium ${imageVerificationClass(ticket)}`}>
                    {imageVerificationLabel(ticket)}
                  </span>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-slate-400">Department</p>
                  <p className="font-medium text-slate-700">{ticket.department_name}</p>
                </div>
                <div>
                  <p className="text-slate-400">Category</p>
                  <p className="font-medium text-slate-700 capitalize">
                    {ticket.category?.replace(/_/g, ' ')}
                  </p>
                </div>
                {ticket.location_text && (
                  <div>
                    <p className="text-slate-400">Location</p>
                    <p className="font-medium text-slate-700 flex items-center gap-1">
                      <MapPin className="w-3 h-3" /> {ticket.location_text}
                    </p>
                  </div>
                )}
                {ticket.latitude && ticket.longitude && (
                  <div>
                    <p className="text-slate-400">GPS</p>
                    <a
                      href={mapsUrl(ticket.latitude, ticket.longitude)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-brand-600 hover:underline flex items-center gap-1"
                    >
                      <ExternalLink className="w-3 h-3" /> Open in Google Maps
                    </a>
                  </div>
                )}
                <div>
                  <p className="text-slate-400">AI Confidence</p>
                  <p className="font-medium text-slate-700">
                    {Math.round((ticket.ai_confidence || 0) * 100)}%
                  </p>
                </div>
              </div>
            </div>
          ))}

          <div className="flex gap-3">
            <button
              onClick={() => { setResult(null); setText(''); setImage(null); setImagePreview(null); setVoiceDraft(null); setVoiceSource(''); }}
              className="flex-1 py-2.5 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 transition"
            >
              Report Another Issue
            </button>
            <button
              onClick={() => navigate('/my-complaints')}
              className="flex-1 py-2.5 bg-white border border-slate-300 text-slate-700 rounded-lg font-medium hover:bg-slate-50 transition"
            >
              View All Complaints
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
