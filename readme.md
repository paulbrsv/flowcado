# Language Learning Algorithm MVP v1

A sophisticated word selection and level assessment algorithm for language learning applications, designed to adapt to user performance and optimize learning outcomes through spaced repetition and intelligent content distribution.

## 🎯 Key Features

- **Adaptive Level Management**: Dynamic difficulty adjustment based on user performance
- **Smart Word Selection**: Intelligent distribution of weak, new, review, and challenge words
- **Spaced Repetition**: Built-in SRS (Spaced Repetition System) with configurable intervals
- **Fallback Strategies**: Multi-level fallback mechanisms to ensure session completion
- **Performance Analytics**: Weighted Success Rate (WSR) calculation for accurate progress tracking
- **Gentle Onboarding**: Specialized first-session experience for new users

## 📊 Configuration Parameters

| Parameter | Default Value | Description |
|-----------|---------------|-------------|
| Starting Level | A2 (difficulty=2) | Initial word difficulty |
| Session Size | 10 words | Words per learning session |
| Quarantine Period | 5 minutes* | Prevents word repetition within session |
| Long Break Threshold | 14 days* | Triggers level freeze after extended pause |
| WSR Weights | 3:2:1* | Weighting for last 3 sessions |
| Level Up Threshold | ≥85%* (3 sessions) | Required performance for level increase |
| Level Down Threshold | <55%* (3 sessions) | Performance threshold for level decrease |
| Max New Words/Session | 5* | Adaptive limit based on performance |
| **Repetition Intervals** | **1/7/30 days*** | **Short/medium/long intervals** |
| **Weak Words Threshold** | **50%*** | **Improved threshold for better adaptation** |
| **Review Words Threshold** | **70%*** | **With backup thresholds and flexible logic** |

*All parameters marked with * are configurable*

## 📚 Word Categories

The algorithm categorizes words into different types based on user performance and learning progress:

### Core Categories

| Category | Condition | Purpose | Priority |
|----------|-----------|---------|----------|
| **Weak** | `difficulty=L AND (success_rate<50% OR last_answer_wrong)` | Reinforce struggling words | High |
| **New-L** | `difficulty=L AND repeats=0` | Introduce new words at current level | Medium/High |
| **Review** | `difficulty=L AND success_rate≥70% AND (now-last_seen)≥interval_short` | Spaced repetition | Medium |
| **Stretch+1** | `difficulty=L+1 AND (repeats=0 OR due)` | Challenge with higher difficulty | Medium/Low |
| **Patch-1** | `difficulty=L-1 AND (repeats=0 OR due_long)` | Fill gaps in foundation | Low |
| **Fallback** | Words selected with relaxed criteria | Guarantee session completion | Variable |

## 🔄 Session Word Distribution

Each 10-word session is carefully balanced across categories:

| Category | Min | Max | Target | Purpose |
|----------|-----|-----|--------|---------|
| Weak | 0 | 3 | 2-3 | Address problem areas |
| New-L | 1 | 5* | Varies by performance | Learn new vocabulary |
| Review | 0 | 3 | 2-3 | Strengthen retention |
| Stretch+1 | 1 | 2 | 1-2 | Provide challenge |
| Patch-1 | 0 | 1 | 1 | Fill knowledge gaps |

### Adaptive New Word Selection

The number of new words introduced per session adapts to user performance:

| Recent Success Rate | New Words Count |
|-------------------|-----------------|
| < 40% | 1 |
| 40-60% | 2 |
| 60-80% | 4 |
| > 80% | 5 |

## 🚀 Onboarding Experience

Special handling for the first two sessions ensures smooth user introduction:

| Session | Composition | Rules |
|---------|-------------|-------|
| **1** | • 5 frequent A1 words (*Easy-A1*)<br>• 5 new A2 words (*New-A2*) | Fixed level, WSR accumulation only |
| **2** | • 3-4 words from session 1<br>• 3-4 new A2 words<br>• 0-2 easy A1 if needed | Level still locked<br>General algorithm starts from session 3 |

## 📈 Level Assessment Algorithm

The system uses a Weighted Success Rate (WSR) calculated from the last 3 sessions:

```
WSR = (S₀×3 + S₁×2 + S₂×1) / 6
```

**Level Adjustment Rules:**
- **Level Up**: 3 consecutive sessions with WSR ≥ 85%
- **Level Down**: 3 consecutive sessions with WSR < 55% (minimum A1)
- **Long Break**: After 14+ day pause, level frozen for 2 sessions, Patch-1 = 3 words

## 🛠️ Architecture Overview

The algorithm is structured as a modular monolith, ready for microservices migration:

### Core Modules

| Module | Responsibility | API |
|--------|---------------|-----|
| **config.py** | Parameter management (JSON/DB) | All modules |
| **db_access.py** | ORM/SQL operations, caching | All business modules |
| **onboarding.py** | First 2 sessions word selection | Session controller |
| **picker.py** | Main word selection algorithm | Session controller |
| **answer_handler.py** | Process user responses, update stats | Answer endpoint |
| **session_evaluator.py** | Calculate WSR, adjust level | After 10 answers |

### Execution Flow

1. **start-session** → `onboarding | picker` → 10 words
2. **answer** → `answer_handler` (update database)
3. **finish-session** → `session_evaluator` (WSR → level adjustment)

## 🔧 Fallback Strategies

The algorithm includes robust fallback mechanisms to handle edge cases:

| Situation | Solution |
|-----------|----------|
| Empty Weak pool | Gradually relax threshold (50% → 65% → 80%) |
| No review words | Search by increasing time periods (1/7/30 days) |
| No New-L words | Search adjacent difficulty levels |
| Insufficient session words | Multi-level fill strategy: pool remainder → sort by recency → random words |
| High performer (>80%) | Increase new words (up to 5) and challenge words (up to 2) |

## 🎯 Key Advantages

- ✅ **Adaptive Balance**: Dynamic adjustment of weak/new/review words based on performance
- ✅ **Smooth Progression**: Gradual level changes without sudden drops
- ✅ **Highly Configurable**: All thresholds and parameters are adjustable
- ✅ **Gentle Onboarding**: Users see quick progress and engagement
- ✅ **Guaranteed Sessions**: Always generates complete 10-word sessions
- ✅ **Performance Optimization**: Enhanced distribution for advanced users
- ✅ **Robust Fallbacks**: Multi-level strategies handle any edge case
- ✅ **Dynamic Adaptation**: New word count adjusts to user success rate
- ✅ **Modular Design**: Clean separation ready for microservices architecture

## 🚀 Getting Started

1. **Configure Parameters**: Adjust default values in configuration file
2. **Initialize Database**: Set up word database with difficulty levels
3. **Implement Modules**: Deploy core modules according to architecture
4. **Start Learning**: Begin with onboarding flow for new users

## 📝 Recent Updates

This version includes several key improvements:
- **Enhanced fallback strategies** for better session completion
- **Improved word distribution** for high-performing users
- **Dynamic new word allocation** based on success rates
- **Flexible threshold management** with backup values
- **Optimized repetition intervals** for better retention

## 🤝 Contributing

This algorithm is designed to be highly adaptable and configurable. All numerical parameters marked with * can be adjusted based on your specific use case and user feedback.

---

*Algorithm specification updated with latest improvements and optimizations.*