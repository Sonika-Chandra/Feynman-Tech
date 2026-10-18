# Demo video script (about 4 minutes, 5:00 at most)

Record the screen at `http://localhost:5000`. Run the backend with the **real AI** (`USE_FAKE_AI=0`) and make sure you have
at least 15 Gemini requests left before you record. Use `test-material/photosynthesis.pdf` as the document.
Do one full rehearsal first, then record.

| Time | On screen | Say |
|---|---|---|
| 0:00-0:25 | The login page | "Students often think they understand a topic because they re-read it. The Feynman technique says you only understand it if you can explain it simply. Vocalis is an AI student that questions you until your gaps show. I create an account and log in." |
| 0:25-0:50 | Upload `photosynthesis.pdf` | "I upload my notes. It accepts PDF, PowerPoint, Word, text, and even a photo of a flowchart. The app finds the topics in the document." |
| 0:50-1:10 | Topic cards, click "The Calvin cycle" | "I pick the topic I want to be tested on and the page turns into a conversation. The AI speaks first." |
| 1:10-1:50 | Tap Speak, answer question 1 out loud (leave one detail out on purpose) | "I explain it out loud, as if teaching a beginner. The words appear as I speak." |
| 1:50-2:30 | Send; the AI asks about the missing detail | "It asks one question about the biggest gap in what I said. It never gives the answer. There are five questions in total." |
| 2:30-3:10 | A diagram question: the whiteboard opens. Draw axes, a box, an arrow, type a label. Send. | "When a question needs a diagram or a graph, a whiteboard opens. I draw and label with the mouse. The AI looks at the picture and tells me how it read it, and that counts as part of my answer." |
| 3:10-3:30 | Answer the remaining questions quickly | "After the fifth question the conversation ends and takes me to my results." |
| 3:30-4:00 | Score ring, four bars, the Gaps tab | "I get a score out of 100 on accuracy, completeness, consistency and clarity, with a reason for each, and a gap report of exactly what I got wrong." |
| 4:00-4:30 | Click "Save gap report", then "Test me on my gaps" | "I can save the report, or upload it straight back. Each gap becomes a topic, so I practise exactly what I got wrong." |
| 4:30-4:50 | Revision notes tab (Kannada), then Home with history | "There is a fact-check, revision notes translated into Kannada, and every session is kept in my history. Built with Flask, SQLite and Gemini; the limits are in our README. Thank you." |

Tips: keep the browser zoom at 100%, close other tabs, mute notifications, and keep each spoken answer under 30 seconds.
