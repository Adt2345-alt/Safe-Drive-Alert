import React, { useState, useEffect, useRef } from 'react';

/**
 * TimePlayback Component
 * Interactive time-series timeline playback controller with scrub slider,
 * play/pause animation, playback speed controls, defect frequency histogram,
 * and defect type/severity filtering.
 */
export default function TimePlayback({
  minTimestamp,
  maxTimestamp,
  currentTimestamp,
  onTimestampChange,
  defects = [],
  selectedTypes = [],
  selectedSeverities = [],
  onTypeFilterChange,
  onSeverityFilterChange
}) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1); // 1x, 2x, 5x, 10x
  const animRef = useRef(null);

  const DEFECT_TYPES = [
    { id: 'pothole', label: 'Potholes', icon: '🕳️' },
    { id: 'crack', label: 'Cracks', icon: '⚡' },
    { id: 'rutting', label: 'Rutting', icon: '〰️' },
    { id: 'marking_degradation', label: 'Markings', icon: '🛣️' },
    { id: 'speedbump', label: 'Speedbumps', icon: '⚠️' }
  ];

  const SEVERITY_LEVELS = [
    { id: 'Critical', label: 'Critical', color: '#ef4444' },
    { id: 'High', label: 'High', color: '#f97316' },
    { id: 'Medium', label: 'Medium', color: '#eab308' },
    { id: 'Low', label: 'Low', color: '#3b82f6' }
  ];

  const startTs = minTimestamp || (Date.now() - 180 * 86400 * 1000);
  const endTs = maxTimestamp || Date.now();
  const currentTs = currentTimestamp || endTs;

  // Animation Loop
  useEffect(() => {
    if (isPlaying) {
      const step = () => {
        onTimestampChange(prev => {
          const delta = (endTs - startTs) / 200 * playbackSpeed;
          const next = (prev || startTs) + delta;
          if (next >= endTs) {
            setIsPlaying(false);
            return endTs;
          }
          return next;
        });
        animRef.current = requestAnimationFrame(step);
      };
      animRef.current = requestAnimationFrame(step);
    } else if (animRef.current) {
      cancelAnimationFrame(animRef.current);
    }

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [isPlaying, playbackSpeed, startTs, endTs, onTimestampChange]);

  const formatDate = (ts) => {
    if (!ts) return '';
    const date = new Date(ts);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const toggleType = (typeId) => {
    if (selectedTypes.includes(typeId)) {
      onTypeFilterChange(selectedTypes.filter(t => t !== typeId));
    } else {
      onTypeFilterChange([...selectedTypes, typeId]);
    }
  };

  const toggleSeverity = (sevId) => {
    if (selectedSeverities.includes(sevId)) {
      onSeverityFilterChange(selectedSeverities.filter(s => s !== sevId));
    } else {
      onSeverityFilterChange([...selectedSeverities, sevId]);
    }
  };

  // Generate 20 histogram bins for frequency distribution
  const bins = Array(25).fill(0);
  const timeStep = (endTs - startTs) / 25;
  defects.forEach(d => {
    if (d.timestamp >= startTs && d.timestamp <= endTs) {
      const binIdx = Math.min(Math.floor((d.timestamp - startTs) / timeStep), 24);
      bins[binIdx]++;
    }
  });
  const maxBinCount = Math.max(...bins, 1);

  return (
    <div style={styles.container}>
      {/* Header & Date Readout */}
      <div style={styles.topRow}>
        <div style={styles.titleSection}>
          <div style={styles.pulseDot} />
          <span style={styles.titleText}>TIME-SERIES DEFECT ACCUMULATION</span>
        </div>
        <div style={styles.dateBadge}>
          <span style={{ color: '#94a3b8', fontSize: '11px', marginRight: '6px' }}>CURRENT VIEW:</span>
          <span style={{ color: '#38bdf8', fontWeight: 600 }}>{formatDate(currentTs)}</span>
          <span style={{ color: '#64748b', margin: '0 8px' }}>/</span>
          <span style={{ color: '#94a3b8' }}>{formatDate(endTs)}</span>
        </div>
      </div>

      {/* Histogram Sparkline */}
      <div style={styles.histogramContainer}>
        {bins.map((count, idx) => {
          const binStartTs = startTs + idx * timeStep;
          const isActive = binStartTs <= currentTs;
          const heightPct = Math.max((count / maxBinCount) * 100, 8);
          return (
            <div
              key={idx}
              title={`${count} defects in ${formatDate(binStartTs)}`}
              style={{
                ...styles.histogramBar,
                height: `${heightPct}%`,
                background: isActive
                  ? 'linear-gradient(180deg, #38bdf8 0%, #0284c7 100%)'
                  : 'rgba(51, 65, 85, 0.4)',
                boxShadow: isActive ? '0 0 8px rgba(56, 189, 248, 0.4)' : 'none'
              }}
            />
          );
        })}
      </div>

      {/* Timeline Scrubbing Slider */}
      <div style={styles.sliderContainer}>
        <input
          type="range"
          min={startTs}
          max={endTs}
          value={currentTs}
          onChange={(e) => onTimestampChange(Number(e.target.value))}
          style={styles.rangeInput}
        />
      </div>

      {/* Control Buttons & Speed Selectors */}
      <div style={styles.controlsRow}>
        <div style={styles.buttonGroup}>
          <button
            onClick={() => onTimestampChange(startTs)}
            style={styles.iconButton}
            title="Reset to Start"
          >
            ⏮
          </button>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            style={styles.playButton}
          >
            {isPlaying ? '⏸ PAUSE' : '▶ PLAY'}
          </button>
          <button
            onClick={() => onTimestampChange(endTs)}
            style={styles.iconButton}
            title="Jump to End"
          >
            ⏭
          </button>
        </div>

        {/* Speed Selector */}
        <div style={styles.speedSelector}>
          {[1, 2, 5, 10].map(speed => (
            <button
              key={speed}
              onClick={() => setPlaybackSpeed(speed)}
              style={{
                ...styles.speedButton,
                background: playbackSpeed === speed ? '#38bdf8' : 'rgba(30, 41, 59, 0.6)',
                color: playbackSpeed === speed ? '#0f172a' : '#94a3b8',
                fontWeight: playbackSpeed === speed ? 700 : 500
              }}
            >
              {speed}x
            </button>
          ))}
        </div>
      </div>

      {/* Filter Chips (Defect Types & Severities) */}
      <div style={styles.filterSection}>
        <div style={styles.filterGroup}>
          <span style={styles.filterLabel}>TYPE:</span>
          {DEFECT_TYPES.map(type => {
            const isSelected = selectedTypes.length === 0 || selectedTypes.includes(type.id);
            return (
              <button
                key={type.id}
                onClick={() => toggleType(type.id)}
                style={{
                  ...styles.filterChip,
                  background: isSelected ? 'rgba(56, 189, 248, 0.15)' : 'rgba(15, 23, 42, 0.4)',
                  borderColor: isSelected ? '#38bdf8' : 'rgba(51, 65, 85, 0.5)',
                  color: isSelected ? '#f8fafc' : '#64748b'
                }}
              >
                <span style={{ marginRight: '4px' }}>{type.icon}</span>
                {type.label}
              </button>
            );
          })}
        </div>

        <div style={styles.filterGroup}>
          <span style={styles.filterLabel}>SEVERITY:</span>
          {SEVERITY_LEVELS.map(sev => {
            const isSelected = selectedSeverities.length === 0 || selectedSeverities.includes(sev.id);
            return (
              <button
                key={sev.id}
                onClick={() => toggleSeverity(sev.id)}
                style={{
                  ...styles.filterChip,
                  background: isSelected ? `${sev.color}22` : 'rgba(15, 23, 42, 0.4)',
                  borderColor: isSelected ? sev.color : 'rgba(51, 65, 85, 0.5)',
                  color: isSelected ? '#f8fafc' : '#64748b'
                }}
              >
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: sev.color, display: 'inline-block', marginRight: '6px' }} />
                {sev.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    position: 'absolute',
    bottom: '24px',
    left: '50%',
    transform: 'translateX(-50%)',
    width: '90%',
    maxWidth: '840px',
    backgroundColor: 'rgba(15, 23, 42, 0.88)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '14px',
    padding: '16px 20px',
    boxShadow: '0 20px 40px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
    zIndex: 30,
    color: '#f8fafc',
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
  },
  topRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px'
  },
  titleSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  },
  pulseDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: '#38bdf8',
    boxShadow: '0 0 10px #38bdf8'
  },
  titleText: {
    fontSize: '11px',
    fontWeight: 700,
    letterSpacing: '1px',
    color: '#94a3b8'
  },
  dateBadge: {
    backgroundColor: 'rgba(30, 41, 59, 0.8)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    padding: '4px 12px',
    borderRadius: '20px',
    fontSize: '12px'
  },
  histogramContainer: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: '3px',
    height: '36px',
    marginBottom: '4px',
    padding: '0 4px'
  },
  histogramBar: {
    flex: 1,
    borderRadius: '2px 2px 0 0',
    transition: 'all 0.2s ease'
  },
  sliderContainer: {
    marginBottom: '12px'
  },
  rangeInput: {
    width: '100%',
    accentColor: '#38bdf8',
    cursor: 'pointer',
    height: '6px',
    borderRadius: '3px',
    backgroundColor: '#334155'
  },
  controlsRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px'
  },
  buttonGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  },
  playButton: {
    backgroundColor: '#38bdf8',
    color: '#0f172a',
    border: 'none',
    borderRadius: '6px',
    padding: '6px 16px',
    fontSize: '12px',
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    boxShadow: '0 0 12px rgba(56, 189, 248, 0.3)'
  },
  iconButton: {
    backgroundColor: 'rgba(30, 41, 59, 0.8)',
    color: '#f8fafc',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '6px',
    padding: '6px 10px',
    fontSize: '12px',
    cursor: 'pointer'
  },
  speedSelector: {
    display: 'flex',
    gap: '4px',
    backgroundColor: 'rgba(15, 23, 42, 0.6)',
    padding: '3px',
    borderRadius: '6px',
    border: '1px solid rgba(255, 255, 255, 0.08)'
  },
  speedButton: {
    border: 'none',
    borderRadius: '4px',
    padding: '3px 8px',
    fontSize: '11px',
    cursor: 'pointer',
    transition: 'all 0.2s ease'
  },
  filterSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    paddingTop: '8px',
    borderTop: '1px solid rgba(255, 255, 255, 0.08)'
  },
  filterGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    flexWrap: 'wrap'
  },
  filterLabel: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#64748b',
    width: '60px',
    letterSpacing: '0.5px'
  },
  filterChip: {
    border: '1px solid',
    borderRadius: '16px',
    padding: '3px 10px',
    fontSize: '11px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    transition: 'all 0.2s ease'
  }
};
