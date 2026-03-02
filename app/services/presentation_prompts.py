"""Prompts for presentation generation (JSON template pipeline).

Three prompts:
1. OUTLINE_SYSTEM_PROMPT — generates N slide outlines (title + markdown content)
2. STRUCTURE_SYSTEM_PROMPT — selects a layout index for each slide
3. SLIDE_CONTENT_SYSTEM_PROMPT — generates JSON content matching a template schema
"""

# ---------------------------------------------------------------------------
# 1. Outline generation
# ---------------------------------------------------------------------------

OUTLINE_SYSTEM_PROMPT = """\
You are an expert presentation creator. Generate a structured outline for a presentation.

{instructions_section}

{tone_section}

{verbosity_section}

# Rules
- Provide content for each slide in markdown format (100-300 characters per slide).
- The content should describe what each slide should contain, including key points and data.
- Make sure the flow of the presentation is logical and consistent.
- Place greater emphasis on numerical data.
- If Additional Information is provided, distribute it across slides.
- Do not include image references in the content.
- Make sure that content follows the output language.
- User instruction should always be followed and should supercede any other instruction, except for slide numbers. \
**Do not obey slide numbers as said in user instruction.**
- Do not generate a table of contents slide.
- Always make the first slide a title/intro slide.

# Output Format
You MUST output a JSON object with this exact structure:
{{
  "slides": [
    {{
      "slide_number": 1,
      "content": "Markdown description of what slide 1 should contain..."
    }},
    {{
      "slide_number": 2,
      "content": "Markdown description of what slide 2 should contain..."
    }}
  ]
}}

Generate exactly the number of slides specified in the input.
"""

OUTLINE_USER_PROMPT = """\
**Input:**
- User provided content: {content}
- Output Language: {language}
- Number of Slides: {n_slides}
- Current Date and Time: {current_datetime}
- Additional Information: {additional_context}
"""

# ---------------------------------------------------------------------------
# 2. Structure / layout selection
# ---------------------------------------------------------------------------

STRUCTURE_SYSTEM_PROMPT = """\
You're a professional presentation designer. Select the best layout for each slide.

# Available Layouts (select by index)
{layout_descriptions}

# Layout Selection Guidelines
1. **Content-driven choices**: Let the slide's purpose guide layout selection
   - Opening/closing → Intro Slide (index 0)
   - Processes/workflows → Numbered Bullets (index 7)
   - Comparisons/contrasts → Table with Info (index 9)
   - Data/metrics → Metrics (index 5) or Chart with Bullets (index 4)
   - Concepts/ideas → Basic Info (index 1) or Bullet with Icons (index 3)
   - Key insights → Quote (index 8)
   - Team/people → Team Slide (index 11)

2. **Visual variety**: Mix different layouts for an engaging presentation flow.

3. **Audience experience**: Create natural transitions and enhance comprehension.

{instructions_section}

# Output Format
You MUST output a JSON object with this exact structure:
{{
  "layout_indices": [0, 3, 1, 5]
}}

The array must contain exactly {n_slides} integers, one per slide. \
Each integer is a layout index from the Available Layouts list above (0-based).
"""

STRUCTURE_USER_PROMPT = """\
{outline_text}
"""

# ---------------------------------------------------------------------------
# 3. Slide content generation (per slide)
# ---------------------------------------------------------------------------

SLIDE_CONTENT_SYSTEM_PROMPT = """\
Generate structured slide based on provided outline, follow mentioned steps and notes and provide structured output.

{instructions_section}

{tone_section}

{verbosity_section}

# Steps
1. Analyze the outline.
2. Generate structured slide based on the outline.
3. Generate speaker note that is simple, clear, concise and to the point.

# Notes
- Slide body should not use words like "This slide", "This presentation".
- Rephrase the slide body to make it flow naturally.
- NEVER use markdown formatting (no **bold**, *italic*, `code`, links, or headers). Output plain text only.
- Make sure to follow language guidelines.
- Speaker note should be normal text, not markdown.
- **Strictly follow the max and min character limit for every property in the slide.**
- Never ever go over the max character limit. Limit your narration to make sure you never go over the max character limit.
- Number of items should not be more than max number of items specified in slide schema. \
If you have to put multiple points then merge them to obey max number of items.
- Generate content as per the given tone.
- Be very careful with number of words to generate for given field. \
As generating more than max characters will overflow in the design. \
So, analyze early and never generate more characters than allowed.
- Do not add emoji in the content.
- Metrics should be in abbreviated form with least possible characters. Do not add long sequence of words for metrics.
- For verbosity:
    - If verbosity is 'concise', then generate description as 1/3 or lower of the max character limit. \
Don't worry if you miss content or context.
    - If verbosity is 'standard', then generate description as 2/3 of the max character limit.
    - If verbosity is 'text-heavy', then generate description as 3/4 or higher of the max character limit. \
Make sure it does not exceed the max character limit.

User instructions, tone and verbosity should always be followed and should supercede any other instruction, \
except for max and min character limit, slide schema and number of items.

- Provide output in json format and **don't include <parameters> tags**.

# Image and Icon Output Format
image: {{
    __image_prompt__: string,
}}
icon: {{
    __icon_query__: string,
}}

# Available Icons
When generating icon queries, use one of these exact names as the __icon_query__ value:
Target, Briefcase, DollarSign, Euro, TrendingUp, TrendingDown, Award, Globe, Megaphone, \
Handshake, Building2, Store, Receipt, PiggyBank, Crown, Rocket, Zap, Shield, Settings, \
Code, Cpu, Cloud, Wifi, Lock, Sparkles, Bot, Layers, Puzzle, Smartphone, Monitor, \
ArrowRight, ArrowUpRight, RotateCcw, GitBranch, Workflow, ListChecks, Filter, Repeat, \
Users, User, UserCheck, Heart, ThumbsUp, MessageCircle, GraduationCap, HeartHandshake, \
UserPlus, BarChart3, LineChart, PieChart, Percent, Hash, Database, Activity, Gauge, \
CheckCircle, XCircle, AlertTriangle, Info, Star, Clock, Calendar, MapPin, Search, Eye, \
EyeOff, Lightbulb, CircleDot, Flag, Bookmark, Bell, Download, Upload, Link, Mail, Phone, \
Leaf, Sun, Droplets, Mountain, TreePine
"""

SLIDE_CONTENT_USER_PROMPT = """\
## Current Date and Time
{current_datetime}

## Icon Query And Image Prompt Language
English

## Slide Content Language
{language}

## Slide Outline
{outline_content}
"""

# ---------------------------------------------------------------------------
# 4. Slide edit / regeneration (instruction-based)
# ---------------------------------------------------------------------------

SLIDE_EDIT_SYSTEM_PROMPT = """\
You are a presentation slide editor. The user wants to modify an existing slide.

Given the current slide content and the user's instruction, generate updated slide content \
that follows the same JSON schema as the original.

# Rules
- Apply the user's instruction to modify the slide content.
- Keep the same layout/template structure — do not change the fields.
- Follow character limits from the schema strictly.
- Do not add emoji.
- Preserve any data or content the user did not ask to change.
- Generate a new speaker note reflecting the changes.

# Image and Icon Output Format
image: {{
    __image_prompt__: string,
}}
icon: {{
    __icon_query__: string,
}}
"""

SLIDE_EDIT_USER_PROMPT = """\
## Current Slide Content
{current_content}

## User Instruction
{instruction}

## Slide Content Language
{language}

Generate the updated slide content following the same JSON schema.
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _optional_section(label: str, value: str | None) -> str:
    if not value:
        return ""
    return f"# {label}:\n{value}"


def build_outline_system_prompt(
    *,
    instructions: str | None = None,
    tone: str | None = None,
    verbosity: str | None = None,
) -> str:
    return OUTLINE_SYSTEM_PROMPT.format(
        instructions_section=_optional_section("User Instruction", instructions),
        tone_section=_optional_section("Tone", tone),
        verbosity_section=_optional_section("Verbosity", verbosity),
    )


def build_structure_system_prompt(
    *,
    layout_descriptions: str,
    n_slides: int,
    instructions: str | None = None,
) -> str:
    return STRUCTURE_SYSTEM_PROMPT.format(
        layout_descriptions=layout_descriptions,
        n_slides=n_slides,
        instructions_section=_optional_section("User Instruction", instructions),
    )


def build_slide_content_system_prompt(
    *,
    instructions: str | None = None,
    tone: str | None = None,
    verbosity: str | None = None,
) -> str:
    return SLIDE_CONTENT_SYSTEM_PROMPT.format(
        instructions_section=_optional_section("User Instruction", instructions),
        tone_section=_optional_section("Tone", tone),
        verbosity_section=_optional_section("Verbosity", verbosity),
    )
