Product Overview: ViralGen AI

ViralGen AI is an asynchronous, multi-modal social media ad content generator designed for marketing teams who need high-velocity campaign variations (50+ daily variations). The system takes a basic text brief, automatically optimizes the prompt, generates highly targeted marketing copy across multiple brand voices, outputs a corresponding high-quality visual, and composites them into a single production-ready marketing asset.
1. Core Feature Areas & Functional Specifications
1.1 Core Workflow: Prompt Refinement Agent

    Description: An invisible AI layer that intercepts a user's basic, non-descriptive brief and maps it into a detailed, visually contextual engineering prompt tailored for image generation models.

    Functional Requirements:

        System must accept raw strings (e.g., "white sneakers").

        The Refinement Agent (powered via Gemini 2.5 Flash / Groq Llama) must output a structurally descriptive visual prompt detailing medium, lighting, camera angles, environment, and style parameters (e.g., "High-fidelity studio photography of minimalist white leather sneakers on a reflective platform, crisp dramatic lighting, product showcase style").

        Prompt templates must automatically apply platform-specific formatting rules (e.g., LinkedIn vs. Instagram aspect ratio defaults).

1.2 Branding Control: Brand Voice Enforcement

    Description: System prompt architecture that restricts and guides the copy generator LLM into specific, predetermined marketing personas.

    Functional Requirements:

        Must support at least three core personas out of the box:

            Professional: Tailored for B2B/LinkedIn, focus on industry metrics, data value, and authoritative, zero-fluff tone.

            Witty: Engaging, human-centric, conversational, uses clever references or subtle humor.

            Urgent: Focused on conversion, FOMO, clear CTA, high impact.

        System prompts must strictly ban generic AI copy cliches (e.g., "Thrilled to share", "Revolutionize your workflow", limit emojis to a maximum of 2).

1.3 Scalability: Asynchronous Generation Pipeline

    Description: A non-blocking task queue architecture designed to handle slow multi-modal generation workloads without tying up web server connections.

    Functional Requirements:

        The main execution endpoint (POST /api/v1/generate) must return a unique job_id and an immediate HTTP 202 Accepted status within under 200ms.

        Image and text creation workloads must be offloaded to an active task worker system.

        A dedicated polling status endpoint (GET /api/v1/status/<job_id>) must communicate task state updates (PENDING, PROCESSING, SUCCESS, FAILED) along with progress logs.

1.4 Asset Processing: Multi-Modal Compositing

    Description: Post-generation image processing layer that unifies text and visuals into a single structural asset.

    Functional Requirements:

        Extract output from the text generation workflow and download the asset from the image generation workflow.

        Utilize programmatic image processing to cleanly handle text layout overlays.

        Resilience Rule: Must dynamically ensure text legibility by rendering a subtle drop shadow or drawing a translucent dark bounding layout block over variable-color images.

2. Implementation Tech Stack

    Language & Framework: Python 3.11+ with FastAPI (native async support, robust docs).

    Text LLM Engine: Google AI Studio API (gemini-2.5-flash) or Groq API (llama-4-scout / llama-3.3-70b) via free-tier developer tokens.

    Image Generation Engine: Hugging Face serverless Inference API (running black-forest-labs/FLUX.1-schnell or stabilityai/stable-diffusion-xl-base-1.0).

    Task Management & Queue: Celery acting as the task worker system.

    Message Broker & Cache: Redis (as the Celery broker and temporary task result store).

    Database & Persistence: MongoDB (to store long-term generation logs, job histories, and configuration mapping state).

    Image Manipulation: Pillow (PIL) for local compositing and typography rendering.

3. 4-Week Implementation Plan
📅 Week 1: Text Generation Framework & Persona Engineering

    Objective: Establish the underlying API framework, connect the free text LLM provider, and build out the brand voice engine.

    Key Tasks & Deliverables:

        Scaffold the FastAPI directory structure.

        Integrate the free text API client wrapper.

        Build specific system prompt configurations for LinkedIn and Instagram across Professional, Witty, and Urgent personas.

    Testing & Quality Assurance: Verify that generated copy strictly respects persona limits (e.g., confirming B2B variants emit zero banned cliches like "Thrilled to share").

📅 Week 2: Free Image Generation Pipeline & Prompt Enhancer

    Objective: Connect to free image endpoints and tie them structurally to the prompt rewriting layer.

    Key Tasks & Deliverables:

        Integrate Hugging Face Inference API client utilizing a free developer token.

        Write the Prompt Enhancer prompt layer that maps casual phrases into high-quality image model instructions.

        Write the basic Pillow processing pipeline to pull text and generated image byte arrays together.

    Testing & Quality Assurance: Consistency checks—send 10 baseline identical briefs (e.g., "running shoes") to verify the Prompt Enhancer creates descriptive, varied, yet consistently high-quality image instructions.

📅 Week 3: Async Queue System & Status Polling

    Objective: Decouple the frontend requests from actual external processing by building the async broker infrastructure.

    Key Tasks & Deliverables:

        Initialize Celery with Redis as the backend broker.

        Port the Week 1 & Week 2 pipeline blocks into individual sequential Celery background tasks.

        Implement the asynchronous status monitoring and retrieval endpoints (/api/v1/status/<job_id>).

    Testing & Quality Assurance: Stress/Load test—dispatch 5 concurrent generation runs to verify the FastAPI main loop remains fully responsive without timing out while Celery handles background execution.

📅 Week 4: Persistent Data Storage & Final End-to-End Delivery

    Objective: Wire up permanent database memory and wrap up the asset production pipeline.

    Key Tasks & Deliverables:

        Set up MongoDB schemas for long-term historical query tracking.

        Implement final Pillow text styling defenses (automatic text-box shading overlays for background color protection).

        Build out a clean unified data response object providing download components, copy variants, and generation telemetry tracking metrics.

    Testing & Quality Assurance: Complete End-to-End (E2E) integration validation—confirm a single input brief smoothly navigates through job generation, returns an accurate tracking payload, runs the task queue worker, saves data logs to MongoDB, and serves up polished, legible multi-modal final output.
