/**
 * Parametric 3D-Printable Y-Piece Blast Gate
 * OpenJSCAD V2 (@jscad/modeling)
 *
 * Print orientation:
 *   - Y-body sits flat on the bed (its underside is the bottom of the tube).
 *   - Slot housings rise vertically; sliders drop in from above (no support needed).
 *   - Sliders are laid flat next to the body for printing.
 */

const jscad = require('@jscad/modeling');
const { cylinder, cuboid, sphere, roundedCuboid } = jscad.primitives;
const { union, subtract } = jscad.booleans;
const { translate, rotateX, rotateZ } = jscad.transforms;

const getParameterDefinitions = () => [
    { name: 'tube_id',          type: 'float', initial: 125, caption: 'Tube Inner Diameter (mm)' },
    { name: 'wall_thickness',   type: 'float', initial: 3,   caption: 'Wall Thickness (mm)' },
    { name: 'conn_length',      type: 'float', initial: 40,  caption: 'Hose Connect Length (mm)' },
    { name: 'angle',            type: 'float', initial: 45,  caption: 'Branch Half-Angle (deg)' },
    { name: 'slider_thickness', type: 'float', initial: 3,   caption: 'Slider Sheet Thickness (mm)' },
    { name: 'tolerance',        type: 'float', initial: 0.3, caption: 'Slider Slip Tolerance (mm)' },
    { name: 'segments',         type: 'int',   initial: 96,  caption: 'Cylinder Segments' }
];

const main = (params) => {
    // -------------------------------------------------------------------------
    // 1. Core dimensions
    // -------------------------------------------------------------------------
    const id     = params.tube_id;
    const wall   = params.wall_thickness;
    const conn   = params.conn_length;
    const aDeg   = params.angle;
    const aRad   = aDeg * Math.PI / 180;
    const slTh   = params.slider_thickness;
    const tol    = params.tolerance;
    const segs   = params.segments;

    const rIn  = id / 2;
    const rOut = rIn + wall;

    // -------------------------------------------------------------------------
    // 2. Slot / housing dimensions (in branch-local frame: Y = branch axis)
    // -------------------------------------------------------------------------
    const sealOverlap = Math.max(8, wall * 2);          // slider extends beyond pipe ID
    const sliderW     = id + 2 * sealOverlap;           // full width of slider sheet
    const slotW       = sliderW + 2 * tol;              // slot width  (X, perpendicular to flow)
    const slotD       = slTh    + 2 * tol;              // slot depth  (Y, along flow)

    const housingW    = slotW + 2 * wall;               // X
    const housingD    = slotD + 2 * wall;               // Y
    const handleClear = 35;                             // exposed handle travel above housing

    // Z extents (body is later lifted so its bottom rests on Z=0)
    const housingZmin = -rOut;                          // flush with tube bottom
    const housingZmax =  rOut + handleClear;
    const housingH    =  housingZmax - housingZmin;
    const housingZmid = (housingZmax + housingZmin) / 2;

    // Slot must clear the entire airway. Leave `wall - 1` of plastic as a stop floor.
    const floorThk    = Math.max(1, wall - 1);
    const slotZmin    = -rOut + floorThk;               // closed-position bottom (acts as stop)
    const slotZmax    =  housingZmax + 1;               // open through the top
    const slotH       =  slotZmax - slotZmin;
    const slotZmid    = (slotZmax + slotZmin) / 2;

    // -------------------------------------------------------------------------
    // 3. Branch geometry — keep housings clear of the central crotch
    // -------------------------------------------------------------------------
    // Distance along branch axis at which the inboard corner of the housing
    // crosses the world Y axis. We keep some margin past that.
    const margin       = 4;
    const minGateOffset = (housingD / 2) +
        ((housingW / 2) * Math.cos(aRad) + margin) / Math.sin(aRad);
    const gateOffset    = Math.max(rOut + wall + 10, minGateOffset);

    const branchLen = gateOffset + housingD / 2 + conn;     // exact: 40mm past housing
    const inletLen  = rOut + conn;                          // 40mm past sphere shell

    // -------------------------------------------------------------------------
    // 4. Helpers
    // -------------------------------------------------------------------------
    // Tube along +Y, starting at origin, length `len`
    const yTube = (radius, len) =>
        translate([0, len / 2, 0],
            rotateX(-Math.PI / 2,
                cylinder({ radius, height: len, segments: segs })));

    const branchOuter = () => union(
        yTube(rOut, branchLen),
        translate([0, gateOffset, housingZmid],
            cuboid({ size: [housingW, housingD, housingH] }))
    );

    // +1mm overshoot avoids coplanar faces at branch open ends
    const branchInner = () => union(
        yTube(rIn, branchLen + 1),
        translate([0, gateOffset, slotZmid],
            cuboid({ size: [slotW, slotD, slotH] }))
    );

    // -------------------------------------------------------------------------
    // 5. Y-body assembly  (sphere at junction guarantees a manifold crotch)
    // -------------------------------------------------------------------------
    const outerShell = union(
        sphere({ radius: rOut, segments: segs }),
        translate([0, -inletLen / 2, 0],
            rotateX(-Math.PI / 2,
                cylinder({ radius: rOut, height: inletLen, segments: segs }))),
        rotateZ( aRad, branchOuter()),
        rotateZ(-aRad, branchOuter())
    );

    const innerVoid = union(
        sphere({ radius: rIn, segments: segs }),
        translate([0, -(inletLen + 1) / 2, 0],
            rotateX(-Math.PI / 2,
                cylinder({ radius: rIn, height: inletLen + 1, segments: segs }))),
        rotateZ( aRad, branchInner()),
        rotateZ(-aRad, branchInner())
    );

    const yBody = translate([0, 0, rOut],   // lift so bottom edge is on Z = 0
        subtract(outerShell, innerVoid));

    // -------------------------------------------------------------------------
    // 6. Slider (gate)
    // -------------------------------------------------------------------------
    const makeSlider = () => {
        // Insert depth must reach the stop floor when handle bottoms out on housing top.
        const insertLen = housingZmax - slotZmin;
        const handleLen = 40;
        const handleW   = sliderW + 30;                 // wider than slot → upper stop
        const tipChamf  = Math.min(4, slTh);            // lead-in at the leading edge
        const overlap   = 0.5;                          // body↔handle CSG overlap

        // Sheet body (Y = 0 .. insertLen). Tip chamfer trimmed off the leading end.
        const sheet = translate([0, insertLen / 2, slTh / 2],
            cuboid({ size: [sliderW, insertLen, slTh] }));

        // Cut a 45° lead-in chamfer along the leading edge (Y = 0)
        const chamfer = translate([0, 0, slTh / 2],
            rotateX(Math.PI / 4,
                cuboid({ size: [sliderW + 2, tipChamf * 2, tipChamf * 2] })));

        const sheetChamfered = subtract(sheet, chamfer);

        // Handle plate (overlaps sheet by `overlap` to ensure a clean union)
        const handleY0 = insertLen - overlap;
        const handleSafeR = Math.min(4, slTh / 2 - 0.01, handleLen / 2 - 0.01);
        const handle = translate([0, handleY0 + handleLen / 2, slTh / 2],
            roundedCuboid({
                size: [handleW, handleLen, slTh],
                roundRadius: handleSafeR,
                segments: 16
            }));

        // Cylindrical finger pull through the handle (more comfortable than a slot)
        const fingerR = Math.min(handleLen / 2 - 6, 12);
        const fingerHole = translate([0, handleY0 + handleLen / 2, slTh / 2],
            cylinder({ radius: fingerR, height: slTh + 2, segments: 48 }));

        return subtract(union(sheetChamfered, handle), fingerHole);
    };

    // Lay sliders flat next to the body (one per branch)
    const sliderClearance = housingW / 2 + 20;
    const slider1 = translate([ rOut + sliderClearance, 0, 0], makeSlider());
    const slider2 = translate([-rOut - sliderClearance, 0, 0], makeSlider());

    return [yBody, slider1, slider2];
};

module.exports = { main, getParameterDefinitions };
