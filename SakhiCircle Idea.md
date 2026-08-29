# SakhiCircle

## Patchamomma 2026 build status

- Idea checkpoint form submitted on 2026-08-21.
- Current platform: locally runnable, mobile-first React/Vite PWA.
- Primary deployment: Firebase Hosting for the website and FastAPI on Cloud Run.
- August 28 goal: one complete sign-in → learning wish → editable journey → explainable match → analytics proof.
- Android source remains frozen historical evidence; production payments and full community operations are deferred.

## One-line pitch

**SakhiCircle helps women reclaim postponed passions, learn alongside women like themselves, and turn lifelong knowledge into purpose and income.**

## The problem

Many women spend decades caring for parents, building careers, managing households, and raising children. In a patriarchal environment, their interests and ambitions are often postponed. When they finally have more time—later in life, after their children become independent, or after retirement—they may want to rediscover old hobbies, learn something new, reconnect with their culture, or share the skills they have developed over a lifetime.

Later-life transitions can also shrink a woman’s social world. Retirement, children moving away, bereavement, relocation, or reduced mobility can interrupt regular contact and a shared sense of purpose. This is more than a lifestyle concern: the World Health Organization reports that social isolation and loneliness can seriously affect health, quality of life, and longevity, with weak social connection carrying a mortality risk comparable to established risks such as smoking. Thoughtfully designed technology can help rebuild connection—not through passive screen time, but by making it easier to find compatible peers, join small trusted groups, practise together, and form recurring real-world relationships.

Existing hobby and community platforms do not adequately address their accessibility needs, life experiences, preferred languages, need for trusted peer groups, or potential to become teachers and earners.

## The solution

SakhiCircle is a voice-first platform where women can **learn, teach, earn, and belong**. It creates personalized learning journeys, connects compatible learning partners, forms small supportive hobby circles, and helps experienced women turn their knowledge into paid lessons or mentorship.

The platform recognizes women as learners, teachers, culture-keepers, mentors, and earners—not merely consumers of hobby activities.

## Primary users

- Women aged 45 and above, including homemakers, working women, empty nesters, and retirees
- Women who want to begin or restart a hobby
- Women who want to preserve and teach cultural or practical skills
- Women seeking peers at a similar life stage
- Women interested in earning through lessons, workshops, or mentorship

## Core features

### 1. Personalized learning journeys

A user selects a hobby or skill and tells SakhiCircle about her experience, goal, available time, language, and accessibility needs. The platform then:

- Generates a realistic daily or weekly learning plan
- Provides short voice-guided activities and instructions
- Tracks completed goals and progress
- Adapts future activities after missed days or difficult tasks
- Adds cultural context and reflection prompts where relevant

Example: A woman who wants to restart Bharatanatyam after 25 years and can practise for 20 minutes on weekdays receives a gentle four-week journey with daily exercises, progress check-ins, and optional mentor sessions.

#### AI-recommended learning resources

For skills that require visual demonstration, such as Kathak, SakhiCircle automatically discovers and recommends relevant YouTube videos instead of generating expensive video content. Its AI recommendation engine evaluates lesson relevance, experience level, preferred language, caption availability, video duration, and learner feedback to create a personalized learning playlist without depending on manual human curation.

SakhiCircle turns each recommended video into part of a structured lesson by adding clear practice steps, accessible alternatives, reflection prompts, progress tracking, peer practice, and optional mentor support. Only videos that pass defined relevance, safety, and quality thresholds are recommended. If no suitable video qualifies, the platform says so rather than presenting an unreliable resource. Original video titles, channels, attribution, YouTube player controls, and advertisements remain intact.

### 2. Teach, mentor, and earn

Women can offer individual lessons, group workshops, structured courses, or ongoing mentorship. SakhiCircle helps them:

- Convert spoken knowledge into a lesson or course plan
- Generate supporting teaching materials
- Set their language, availability, format, and price
- Accept bookings and payments
- Build a trusted teaching profile through reviews and completed sessions

This creates income opportunities while preserving traditional, creative, and practical knowledge.

### 3. Learning-partner matching

SakhiCircle matches women working toward similar goals using factors such as:

- Hobby and learning objective
- Current skill level
- Preferred language
- Availability and learning pace
- Online or nearby participation preference

For example, two women restarting classical music can be paired for twice-weekly practice and mutual encouragement.

### 4. Sakhi Circles

Users can join small, supportive learning circles based on a shared hobby or goal. A circle can include:

- Group check-ins and progress sharing
- Practice sessions and workshops
- Questions for mentors
- Celebration of milestones
- Encouragement after missed goals

These are positioned as **supportive learning circles**, without claiming to treat loneliness or any mental-health condition.

### 5. Voice-first, accessible experience

The interface prioritizes voice interaction, familiar languages, clear navigation, and adjustable text. Users should be able to join, describe a skill, receive a plan, and record progress without needing strong technical or typing skills.

## MVP demonstration

The August 28 demonstration follows one connected journey:

1. A learner enters through a configured sign-in state or explicit development demo.
2. She speaks or types a hobby she postponed earlier in life and confirms the extracted fields.
3. SakhiCircle creates an editable four-week bilingual learning plan.
4. The platform explains a compatible peer or mentor match from synthetic data.
5. A pseudonymous journey or recommendation event appears in a small BigQuery/Looker Studio proof.

Full circles, booking, payments, mentor earnings, and production marketplace operations remain product-roadmap capabilities rather than checkpoint dependencies.

## Technology direction

- **React/Vite PWA:** Mobile-first browser experience that also works on desktop and can run locally
- **Gemini + bounded ADK workflow:** Learning-plan generation, accessibility/safety review, and English/Hindi localization
- **Firebase:** Authentication, Firestore operational data, local emulators, and Hosting
- **Cloud Run:** FastAPI services and secure Gemini integration
- **YouTube Data API:** Automated discovery and metadata-based ranking of embeddable learning videos and playlists
- **Google Maps:** Optional discovery of nearby circles or sessions
- **BigQuery:** Anonymized engagement and impact analytics
- **Looker Studio:** Dashboards for program organizers and impact reporting

## Business model

- Small commission on paid lessons, workshops, and mentorship sessions
- Optional premium plans for advanced learning journeys or additional mentor access
- Partnerships with senior communities, cultural organizations, NGOs, and employers
- Sponsored learning circles or community programs

The checkpoint MVP validates learning-plan usefulness, explainable matching, and measurable engagement before adding paid mentor bookings or multiple revenue streams.

## Success measures

- Learning plans started and completed
- Repeat participation and active learning days
- Partner and circle engagement
- Skills taught or transferred
- Paid mentor sessions completed
- Income generated by mentors
- User-reported progress toward personal goals

## Safety and trust

- Require consent before sharing profile or location information
- Keep exact location private unless a user explicitly chooses otherwise
- Use reporting, blocking, mentor verification, and review tools
- Use curated templates and clear cautions for physical or health-related activities
- Use evidence about social isolation to explain the need for connection, while avoiding claims that SakhiCircle diagnoses, treats, or prevents loneliness or any health condition
- Explain how matches and generated plans are created

## Evidence

- [World Health Organization: Reducing social isolation and loneliness among older people](https://www.who.int/health-topics/ageing/reducing-social-isolation-and-loneliness-among-older-people)
- [World Health Organization: Commission on Social Connection](https://www.who.int/groups/technical-advisory-group-on-social-connection-%28tag-sc%29)
- [YouTube Data API: Search](https://developers.google.com/youtube/v3/docs/search/list)
- [YouTube API Services: Developer Policies](https://developers.google.com/youtube/terms/developer-policies-guide)

## Differentiator

SakhiCircle is not merely a hobby marketplace or social network. It combines personalized AI learning plans, peer matching, supportive circles, cultural preservation, mentorship, and income generation in one accessible experience designed around women in later stages of life.

## Central story

**She spent years caring for everyone else. SakhiCircle gives her the space to rediscover herself.**
