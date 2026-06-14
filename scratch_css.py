import os

css_content = """

/* Planetary Chart */
.planet-chart-container {
  position: relative;
  width: 100%;
  height: 600px;
  background: #000;
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: center;
}

.galaxy-stars {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background-image: 
    radial-gradient(1px 1px at 20px 30px, #eee, rgba(0,0,0,0)),
    radial-gradient(1px 1px at 40px 70px, #fff, rgba(0,0,0,0)),
    radial-gradient(1.5px 1.5px at 90px 40px, #fff, rgba(0,0,0,0));
  background-repeat: repeat;
  background-size: 200px 200px;
  opacity: 0.3;
  z-index: 1;
}

.planet-controls {
  position: absolute;
  top: 16px;
  right: 16px;
  display: flex;
  gap: 8px;
  z-index: 10;
}

.planet-controls button {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: var(--text);
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.planet-controls button.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #000;
  font-weight: bold;
}

.planet-mode-readout {
  position: absolute;
  top: 16px;
  left: 20px;
  color: var(--text);
  z-index: 10;
  display: flex;
  flex-direction: column;
}

.planet-mode-readout strong {
  font-size: 16px;
  color: var(--accent);
  margin-bottom: 4px;
}

.planet-mode-readout span {
  font-size: 12px;
  color: var(--muted);
}

.galaxy-disc {
  position: relative;
  width: 100%;
  height: 100%;
  z-index: 2;
  perspective: 1000px;
}

.planet-center {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 10px;
  height: 10px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: white;
  box-shadow: 0 0 40px 20px rgba(255, 255, 255, 0.2);
}

.planet-node {
  position: absolute;
  border-radius: 50%;
  border: none;
  padding: 0;
  cursor: pointer;
  transition: transform 0.3s ease, filter 0.3s ease;
  transform-style: preserve-3d;
  animation: orbit-rotate 60s linear infinite;
  animation-delay: var(--planet-delay);
  /* Use transform-origin to rotate around center? No, we used absolute positions px, py. So we just let them stay or animate slowly */
}

.planet-node:hover {
  transform: scale(1.15);
  z-index: 100;
  filter: brightness(1.2);
}

.planet-node-content {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  color: white;
  font-size: 11px;
  font-weight: bold;
  text-align: center;
  overflow: hidden;
  word-break: break-all;
  padding: 4px;
}

.planet-tooltip {
  position: fixed;
  background: rgba(10, 15, 20, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 12px;
  border-radius: 8px;
  color: white;
  z-index: 1000;
  pointer-events: none;
  backdrop-filter: blur(4px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
"""

with open('/Users/maxyu/Documents/台股資金網站/web/src/styles.css', 'a') as f:
    f.write(css_content)
print("Appended CSS successfully.")
