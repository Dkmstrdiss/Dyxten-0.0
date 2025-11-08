import os, sys, time
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from core.view.view_widget import DyxtenEngine

# Instantiate engine
engine = DyxtenEngine()
# Configure higher particle count for better collision probability
engine.state.setdefault('system', {})['Nmax'] = 4000
engine.state.setdefault('appearance', {})['px'] = 3.0
engine.state.setdefault('camera', {})['omegaDegPerSec'] = 60
# Apply updated params
engine.set_params({'system': engine.state['system'], 'appearance': engine.state['appearance'], 'camera': engine.state['camera']})

w, h = 800, 600
imprint_counts = []
for frame in range(300):
    engine.step(w, h)
    imprint_counts.append(len(engine._imprints))
    time.sleep(0.002)

print('Total frames:', len(imprint_counts))
print('Final imprint count:', len(engine._imprints))
print('Imprint count progression sample (first 20):', imprint_counts[:20])
print('Any imprint created?', any(c>0 for c in imprint_counts))
print('Sample imprint entries:', engine._imprints[:5])
