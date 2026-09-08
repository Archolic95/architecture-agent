export function orthographicHeight(distance,fovDegrees,zoom=1){return 2*distance*Math.tan(fovDegrees*Math.PI/360)/zoom;}
export function perspectiveDistance(height,fovDegrees,zoom=1){return height*zoom/(2*Math.tan(fovDegrees*Math.PI/360));}
export function sectionCoordinate(min,max,percentage){return min+(max-min)*Math.max(0,Math.min(100,percentage))/100;}
export function rowMajorToColumnMajor(matrix){return Array.from({length:16},(_,i)=>matrix[(i%4)*4+Math.floor(i/4)]);}

// Keep useful depth precision for thin adjacent architectural parts. A near
// plane at diameter/10000 and far at diameter*1000 loses centimetres at Fit.
export function modelClipRange(diameter, distance) {
  const size = Math.max(diameter, 0.001);
  return {near: Math.max(size * 1e-5, Math.min(size * 0.005, Math.max(distance, size * 1e-5) * 0.002)),
          far: Math.max(distance + size * 5, size * 10, 1)};
}
