import { useEffect, useRef } from "react";

interface WaveformProps {
  analyser: AnalyserNode | null;
  color?: string;
}

export function Waveform({ analyser, color = "#f4c542" }: WaveformProps): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !analyser) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const dpr = window.devicePixelRatio || 1;
    const resize = () => {
      const { width, height } = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
    };
    resize();
    window.addEventListener("resize", resize);

    const data = new Uint8Array(analyser.fftSize);
    let frameId = 0;
    const draw = () => {
      analyser.getByteTimeDomainData(data);
      const { width, height } = canvas;
      context.clearRect(0, 0, width, height);
      context.lineWidth = 2 * dpr;
      context.strokeStyle = color;
      context.shadowColor = color;
      context.shadowBlur = 8 * dpr;
      context.beginPath();
      const step = width / data.length;
      data.forEach((sample, index) => {
        const x = index * step;
        const y = (sample / 255) * height;
        if (index === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      });
      context.stroke();
      frameId = requestAnimationFrame(draw);
    };
    frameId = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", resize);
    };
  }, [analyser, color]);

  return <canvas ref={canvasRef} className="waveform-canvas" aria-hidden="true" />;
}
