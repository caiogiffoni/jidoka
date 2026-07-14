# Product

## Register

product

## Platform

web

## Users

Primary: Caio, running his own work on the board every day - planning tasks, dragging cards, chatting with the agent, tracking time. The design must survive real daily use, not just a staged demo.

Secondary: public users, in a later phase. Jidoka opens to registered users, and a no-signup demo space lets anyone - first-time visitors, interviewers, hiring engineers - try the board and the agent without creating an account. These visitors spend 2–10 minutes in the demo before deciding to register (or to keep reading the repo). When a design decision conflicts between the two audiences, pick what reads best in that short first-touch session - the unregistered demo visitor is the tiebreaker.

## Product Purpose

Jidoka is a Trello-style kanban board operated both by hand and by an LLM agent with human-in-the-loop approval. The agent proposes changes as a diff; nothing touches the board until the human approves. Success means it becomes a genuinely useful tool - Caio keeps using it after the job search, and the portfolio effect is a byproduct of it being real.

## Positioning

**Agent proposes, you decide.** The board where an AI does the work but never acts without your approval - human-in-the-loop is the identity, not a feature.

## Brand Personality

Confident energy: fast, alive, a little showy. The interface should feel like a machine visibly at work - streaming agent actions, cards moving live, optimistic drag with weight - while never hiding that a human holds the approve/reject lever. Tactile like Trello's board at its best; sharp and high-contrast like the Vercel dashboard, where a streaming log feels alive.

## Anti-references

- **Jira / enterprise PM tools**: heavy chrome, nested configuration, ten toolbars, blue-gray corporate density. Jidoka stays a board, not a platform.
- **AI-chatbot-first UI**: a chat window with a board bolted on - sparkle emoji, purple-gradient "AI magic" branding, agent theater. The board is the main surface; chat drives it, it doesn't replace it.

## Design Principles

1. **Agent proposes, you decide.** The approval moment (diff → approve/reject/edit) is the hero interaction of the whole product. Make human control visible everywhere the agent acts.
2. **The board is the show.** Agent activity expresses itself as the board moving - cards appearing, sliding, updating live - not as chat transcript theater.
3. **Real tool first.** Every surface must survive daily use: honest empty states, loading skeletons, error recovery. Demo shine is earned by real states, not staged ones.
4. **Speed is the personality.** Optimistic updates, tactile drag, instant feedback, streaming everywhere. Confident energy comes from responsiveness, not decoration.
5. **Legible in ten minutes.** A first-time demo visitor should grasp the HITL architecture from the UI alone - proposals, diffs, and applied changes each look distinct at a glance.

## Accessibility & Inclusion

WCAG 2.1 AA: ≥4.5:1 body-text contrast (3:1 for large text), full keyboard support including keyboard-operable drag-and-drop via dnd-kit's keyboard sensor, visible focus states, and `prefers-reduced-motion` alternatives for every animation.
