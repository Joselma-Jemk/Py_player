# PyPlayer Performance Benchmark Results

## Executive Summary

Comprehensive profiling of PyPlayer startup and runtime operations revealed critical performance bottlenecks:

| Component | Time | Impact |
|-----------|------|--------|
| **QVideoWidget creation** | ~2077 ms | **CRITICAL** - 80% of MainWindow creation |
| QAudioOutput creation | ~307 ms | MEDIUM |
| Imports | ~328 ms | MEDIUM |
| PlaylistManager boot (50 playlists) | ~727 ms | MEDIUM |
| addWidget (Qt layout) | ~377 ms (total) | MEDIUM |
| addApplicationFont | ~167 ms (total) | LOW |

## 1. Startup Performance

### Cold Startup Breakdown
```
Total estimated: ~7230 ms
- Imports:                328 ms  (4.5%)
- QApplication creation:   53 ms   (0.7%)
- PlaylistManager (empty): 22 ms   (0.3%)
- MainWindow creation:   6827 ms  (94.4%)
```

### MainWindow Creation Breakdown
```
Total: ~4421 ms (profiled)
- PlayerWidget.create_widgets: 3522 ms (79.7%) ⚠️
- addWidget calls (Qt):        377 ms (8.5%)
- addApplicationFont (3x):     167 ms (3.8%)
- Other widget init:           355 ms (8.0%)
```

### QtMultimedia Initialization Costs
```
QVideoWidget creation:   2077 ms ⚠️ CRITICAL
QAudioOutput creation:    307 ms  MEDIUM
QMediaPlayer creation:      3 ms  NEGLIGIBLE
setVideoOutput:             0 ms  NEGLIGIBLE
setAudioOutput:             0 ms  NEGLIGIBLE
```

**Key Insight:** First QVideoWidget creation is expensive (~2s), subsequent creations are fast (~2ms). This suggests one-time backend initialization.

## 2. Playlist Domain Performance

### Playlist Creation
| Videos | Time | Per Video |
|--------|------|-----------|
| 10     | 14 ms | 1.43 ms |
| 100    | 106 ms| 1.06 ms |
| 500    | 773 ms| 1.55 ms |
| 1000   | 1987 ms| 1.99 ms |

**Observation:** Linear growth, ~1-2ms per video. Acceptable for typical use (<100 videos).

### Save/Load Operations
| Videos | Save | Load |
|--------|------|------|
| 10     | 7 ms  | 18 ms |
| 100    | 16 ms | 20 ms |
| 500    | 88 ms | 92 ms |

**Observation:** I/O is not a bottleneck. JSON serialization/deserialization is efficient.

### Navigation Performance (100 iterations)
| Mode   | Time | Per Operation |
|--------|------|---------------|
| NORMAL | 3.2 ms| 0.032 ms |
| LOOP_ALL| 1.7 ms| 0.017 ms |
| SHUFFLE | 1.6 ms| 0.016 ms |

**Observation:** Navigation is extremely fast. Not a priority for optimization.

### Shuffle Generation
| Videos | Time |
|--------|------|
| 100    | 0.1 ms|
| 500    | 0.3 ms|
| 1000   | 0.6 ms|
| 5000   | 3.2 ms|

**Observation:** Negligible cost. Not a priority.

### Batch Video Addition (500 videos)
| Batch Size | Time | Per Video |
|------------|------|-----------|
| 1          | 154 ms| 0.31 ms |
| 10         | 186 ms| 0.37 ms |
| 50         | 145 ms| 0.29 ms |
| 100        | 176 ms| 0.35 ms |

**Observation:** Minimal variation. Not a priority.

## 3. I/O Performance

### find_path Performance
| Mode     | Time (100 searches) | Per Search |
|----------|---------------------|------------|
| Cached   | 53 ms | 0.53 ms |
| Uncached | 51 ms | 0.51 ms |

**Observation:** Cache doesn't significantly help. Search is already fast (~0.5ms).

### JSON Write/Read (Atomic)
| Size | Write | Read |
|------|-------|------|
| 10 KB| 7 ms  | 24 ms|
| 100 KB| 8 ms  | 34 ms|
| 500 KB| 23 ms | 31 ms|
| 1000 KB|21 ms | 21 ms|

**Observation:** Atomic write is efficient. Not a bottleneck.

### Directory Scan
| Files | Time | Per File |
|-------|------|----------|
| 10    | 3 ms  | 0.26 ms |
| 100   | 2 ms  | 0.02 ms |
| 500   | 3 ms  | 0.01 ms |
| 1000  | 10 ms | 0.01 ms |

**Observation:** Very efficient. Not a bottleneck.

### File Exists Check
| Checks | Time | Per Check |
|--------|------|-----------|
| 100    | 7 ms  | 0.07 ms |
| 500    | 24 ms | 0.05 ms |
| 1000   | 96 ms | 0.10 ms |

**Observation:** Acceptable. Not a priority.

### Recursive find_path
| Depth | Time |
|-------|------|
| 3     | 1.6 ms|
| 5     | 2.0 ms|
| 10    | 3.3 ms|

**Observation:** Efficient even at depth 10. Not a bottleneck.

## 4. Critical Hotspots Identified

### P0 - CRITICAL (Must Fix)
1. **QVideoWidget initialization (~2077 ms)**
   - Location: `src/pyplayer/ui/widgets/player.py:89`
   - Impact: 80% of MainWindow creation, ~29% of total startup
   - Root cause: FFmpeg backend initialization on first widget creation

### P1 - HIGH (Should Fix)
2. **QAudioOutput initialization (~307 ms)**
   - Location: `src/pyplayer/ui/widgets/player.py:90`
   - Impact: ~4% of total startup
   - Root cause: Audio backend initialization

3. **PlaylistManager boot with many playlists**
   - Impact: ~727 ms for 50 playlists (~14ms/playlist)
   - Scenarios: Users with many saved playlists

### P2 - MEDIUM (Nice to Have)
4. **addWidget calls in layouts**
   - Total: ~377 ms across 22 calls
   - Average: ~17 ms per call
   - Impact: Minor, but could be optimized

5. **Font loading (addApplicationFont)**
   - Total: ~167 ms for 3 loads
   - Average: ~56 ms per load
   - Impact: Minor, icon fonts

## 5. NOT Bottlenecks (Don't Optimize)

- Playlist creation/navigation: Already efficient
- JSON serialization/deserialization: Fast
- Directory scanning: Efficient
- File I/O: Not problematic
- find_path: Acceptable performance

## 6. Optimization Prioritization

### Prompt 2 (First Wave - Maximum Impact)
1. **Delay QVideoWidget creation** - Create on-demand when first video is played
2. **Delay QAudioOutput creation** - Create on-demand when first video is played
3. **Lazy PlaylistManager data loading** - Load playlists in background

### Prompt 3 (Second Wave - Refinement)
4. **Optimize layout.addWidget calls** - Consider batch updates
5. **Cache font loading** - Load fonts once, reuse
6. **Optimize PlaylistManager boot** - Consider parallel loading

### NOT Priority (Skip)
- Playlist operations (already fast)
- I/O operations (not bottlenecks)
- Navigation (extremely fast)
