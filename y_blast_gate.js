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
const primitives = jscad.primitives;
const booleans = jscad.booleans;
const transforms = jscad.transforms;

const cylinder      = primitives.cylinder;
const cuboid        = primitives.cuboid;
const sphere        = primitives.sphere;
const roundedCuboid = primitives.roundedCuboid;
const union         = booleans.union;
const subtract      = booleans.subtract;
const translate     = transforms.translate;
const rotateX       = transforms.rotateX;
const rotateZ       = transforms.rotateZ;

function getParameterDefinitions() {
    return [
        { name: 'tube_id',          type: 'float', initial: 125, caption: 'Tube Inner Diameter (mm)' },
        { name: 'wall_thickness',   type: 'float', initial: 3,   caption: 'Wall Thickness (mm)' },
        { name: 'conn_length',      type: 'float', initial: 40,  caption: 'Hose Connect Length (mm)' },
        { name: 'angle',            type: 'float', initial: 45,  caption: 'Branch Half-Angle (deg)' },
        { name: 'slider_thickness', type: 'float', initial: 3,   caption: 'Slider Sheet Thickness (mm)' },
        { name: 'tolerance',        type: 'float', initial: 0.3, caption: 'Slider Slip Tolerance (mm)' },
        { name: 'segments',         type: 'int',   initial: 96,  caption: 'Cylinder Segments' }
    ];
}

function main(params) {
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
    const sealOverlap = Math.max(8, wall * 2);
    const sliderW     = id + 2 * sealOverlap;
    const slotW       = sliderW + 2 * tol;
    const slotD       = slTh    + 2 * tol;

    const housingW    = slotW + 2 * wall;
    const housingD    = slotD + 2 * wall;
    const handleClear = 35;

    const housingZmin = -rOut;
    const housingZmax =  rOut + handleClear;
    const housingH    =  housingZmax - housingZmin;
    const housingZmid = (housingZmax + housingZmin) / 2;

    const floorThk    = Math.max(1, wall - 1);
    const slotZmin    = -rOut + floorThk;
    const slotZmax    =  housingZmax + 1;
    const slotH       =  slotZmax - slotZmin;
    const slotZmid    = (slotZmax + slotZmin) / 2;

    // -------------------------------------------------------------------------
    // 3. Branch geometry — keep housings clear of the central crotch
    // -------------------------------------------------------------------------
    const margin        = 4;
    const minGateOffset = (housingD / 2) +
        ((housingW / 2) * Math.cos(aRad) + margin) / Math.sin(aRad);
    const gateOffset    = Math.max(rOut + wall + 10, minGateOffset);

    const branchLen = gateOffset + housingD / 2 + conn;
    const inletLen  = rOut + conn;

    // -------------------------------------------------------------------------
    // 4. Helpers
    // -------------------------------------------------------------------------
    function yTube(radius, len) {
        return translate([0, len / 2, 0],
            rotateX(-Math.PI / 2,
                cylinder({ radius: radius, height: len, segments: segs })));
    }

    function branchOuter() {
        return union(
            yTube(rOut, branchLen),
            translate([0, gateOffset, housingZmid],
                cuboid({ size: [housingW, housingD, housingH] }))
        );
    }

    function branchInner() {
        return union(
            yTube(rIn, branchLen + 1),
            translate([0, gateOffset, slotZmid],
                cuboid({ size: [slotW, slotD, slotH] }))
        );
    }

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

    const yBody = translate([0, 0, rOut],
        subtract(outerShell, innerVoid));

    // -------------------------------------------------------------------------
    // 6. Slider (gate)
    // -------------------------------------------------------------------------
    function makeSlider() {
        const insertLen = housingZmax - slotZmin;
        const handleLen = 40;
        const handleW   = sliderW + 30;
        const tipChamf  = Math.min(4, slTh);
        const overlap   = 0.5;

        const sheet = translate([0, insertLen / 2, slTh / 2],
            cuboid({ size: [sliderW, insertLen, slTh] }));

        const chamfer = translate([0, 0, slTh / 2],
            rotateX(Math.PI / 4,
                cuboid({ size: [sliderW + 2, tipChamf * 2, tipChamf * 2] })));

        const sheetChamfered = subtract(sheet, chamfer);

        const handleY0    = insertLen - overlap;
        const handleSafeR = Math.min(4, slTh / 2 - 0.01, handleLen / 2 - 0.01);
        const handle = translate([0, handleY0 + handleLen / 2, slTh / 2],
            roundedCuboid({
                size: [handleW, handleLen, slTh],
                roundRadius: handleSafeR,
                segments: 16
            }));

        const fingerR = Math.min(handleLen / 2 - 6, 12);
        const fingerHole = translate([0, handleY0 + handleLen / 2, slTh / 2],
            cylinder({ radius: fingerR, height: slTh + 2, segments: 48 }));

        return subtract(union(sheetChamfered, handle), fingerHole);
    }

    const sliderClearance = housingW / 2 + 20;
    const slider1 = translate([ rOut + sliderClearance, 0, 0], makeSlider());
    const slider2 = translate([-rOut - sliderClearance, 0, 0], makeSlider());

    return [yBody, slider1, slider2];
}

module.exports = { main: main, getParameterDefinitions: getParameterDefinitions };
