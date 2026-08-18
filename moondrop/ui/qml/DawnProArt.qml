import QtQuick
import QtQuick.Shapes

/*
 * A vector diagram of the Dawn Pro, drawn from MOONDROP's product photography:
 * an aluminium block seen three-quarters from the front left, with the
 * perforated grille across the top face, the engraving along the long face and
 * the 3.5 mm / 4.4 mm jacks on the near end.
 *
 * Two details make it read as the real object rather than a plain box:
 *
 *  - Every face is a *rounded* polygon. The real body is milled with generously
 *    radiused edges, so each face path cuts its corners with quadratic curves,
 *    and a silhouette underneath fills the slivers where the rounded faces pull
 *    away from one another.
 *  - Each face carries an affine transform mapping face-local coordinates onto
 *    the screen, so the grille dots, the engraving and the jack circles are laid
 *    out in the natural coordinates of the face they sit on and get sheared into
 *    place. Circles become the correct ellipses on their own.
 */
Item {
    id: art

    property color accent: "#22D3EE"
    property bool ledOn: true
    property real edgeRadius: 7

    implicitWidth: 380
    implicitHeight: 200

    // --- geometry --------------------------------------------------------
    // Origin is the top-front-left corner; the body runs up and to the right.
    readonly property point origin: Qt.point(24, 96)
    readonly property point vLength: Qt.point(245.4, -85.9)  // along the body
    readonly property point vWidth: Qt.point(73.9, 41.9)     // across, foreshortened
    readonly property real vHeight: 52                       // straight down

    readonly property real lenNorm: Math.hypot(vLength.x, vLength.y)
    readonly property real widthNorm: Math.hypot(vWidth.x, vWidth.y)
    readonly property point uLength: Qt.point(vLength.x / lenNorm, vLength.y / lenNorm)
    readonly property point uWidth: Qt.point(vWidth.x / widthNorm, vWidth.y / widthNorm)

    // l, w and h are each 0 or 1: which of the block's eight corners.
    function corner(l, w, h) {
        return Qt.point(origin.x + vLength.x * l + vWidth.x * w,
                        origin.y + vLength.y * l + vWidth.y * w + vHeight * h)
    }

    // SVG path for a closed polygon whose corners are rounded off with
    // quadratic curves. The radius is clamped per corner so a short edge cannot
    // over-round and fold back on itself.
    function roundedPath(points, radius) {
        const n = points.length
        let d = ""
        for (let i = 0; i < n; ++i) {
            const cur = points[i]
            const prev = points[(i - 1 + n) % n]
            const next = points[(i + 1) % n]

            const toPrev = Qt.point(prev.x - cur.x, prev.y - cur.y)
            const toNext = Qt.point(next.x - cur.x, next.y - cur.y)
            const lenPrev = Math.hypot(toPrev.x, toPrev.y)
            const lenNext = Math.hypot(toNext.x, toNext.y)
            const r = Math.min(radius, lenPrev / 2, lenNext / 2)

            const a = Qt.point(cur.x + toPrev.x / lenPrev * r,
                               cur.y + toPrev.y / lenPrev * r)
            const b = Qt.point(cur.x + toNext.x / lenNext * r,
                               cur.y + toNext.y / lenNext * r)

            d += (i === 0 ? "M " : "L ") + a.x + "," + a.y + " "
            d += "Q " + cur.x + "," + cur.y + " " + b.x + "," + b.y + " "
        }
        return d + "Z"
    }

    readonly property var topFace: [corner(0, 0, 0), corner(1, 0, 0),
                                    corner(1, 1, 0), corner(0, 1, 0)]
    readonly property var longFace: [corner(0, 1, 0), corner(1, 1, 0),
                                     corner(1, 1, 1), corner(0, 1, 1)]
    readonly property var endFace: [corner(0, 0, 0), corner(0, 1, 0),
                                    corner(0, 1, 1), corner(0, 0, 1)]
    // Outline of the whole block, filling the seams between the rounded faces.
    readonly property var silhouette: [corner(0, 0, 0), corner(1, 0, 0), corner(1, 1, 0),
                                       corner(1, 1, 1), corner(0, 1, 1), corner(0, 0, 1)]

    Item {
        anchors.centerIn: parent
        width: 380
        height: 200
        scale: Math.min(art.width / 380, art.height / 200)
        transformOrigin: Item.Center

        // Contact shadow --------------------------------------------------
        Rectangle {
            x: 74
            y: 178
            width: 220
            height: 10
            radius: 5
            color: "#000000"
            opacity: 0.16
        }

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer

            // Body silhouette, so nothing shows through where the rounded
            // faces pull away from one another.
            ShapePath {
                strokeWidth: 1
                strokeColor: Qt.rgba(0, 0, 0, 0.32)
                fillColor: "#A9AEB7"
                PathSvg { path: art.roundedPath(art.silhouette, art.edgeRadius) }
            }

            // Top face ----------------------------------------------------
            ShapePath {
                strokeWidth: 0
                fillGradient: LinearGradient {
                    x1: 24; y1: 10; x2: 343; y2: 138
                    GradientStop { position: 0.0; color: "#F1F3F6" }
                    GradientStop { position: 0.45; color: "#DDE0E6" }
                    GradientStop { position: 1.0; color: "#BFC4CC" }
                }
                PathSvg { path: art.roundedPath(art.topFace, art.edgeRadius) }
            }

            // Long face, the one carrying the engraving --------------------
            ShapePath {
                strokeWidth: 0
                fillGradient: LinearGradient {
                    x1: 98; y1: 138; x2: 343; y2: 90
                    GradientStop { position: 0.0; color: "#C9CDD4" }
                    GradientStop { position: 0.55; color: "#AEB3BB" }
                    GradientStop { position: 1.0; color: "#8E939C" }
                }
                PathSvg { path: art.roundedPath(art.longFace, art.edgeRadius) }
            }

            // Near end face, the one carrying the jacks --------------------
            ShapePath {
                strokeWidth: 0
                fillGradient: LinearGradient {
                    x1: 24; y1: 96; x2: 98; y2: 190
                    GradientStop { position: 0.0; color: "#A8ADB6" }
                    GradientStop { position: 1.0; color: "#7A7F89" }
                }
                PathSvg { path: art.roundedPath(art.endFace, art.edgeRadius) }
            }
        }

        // --- top face contents: the perforated grille ---------------------
        Item {
            transform: Matrix4x4 {
                matrix: Qt.matrix4x4(art.uLength.x, art.uWidth.x, 0, art.origin.x,
                                     art.uLength.y, art.uWidth.y, 0, art.origin.y,
                                     0, 0, 1, 0,
                                     0, 0, 0, 1)
            }

            Repeater {
                model: 13 * 6
                delegate: Rectangle {
                    required property int index
                    readonly property int row: Math.floor(index / 13)
                    readonly property int column: index % 13

                    x: 58 + column * 12 - width / 2
                    y: 15 + row * 11 - height / 2
                    width: 5
                    height: 5
                    radius: 2.5
                    color: "#7C828C"
                    opacity: 0.85
                }
            }
        }

        // --- long face contents: the engraving ----------------------------
        Item {
            transform: Matrix4x4 {
                matrix: Qt.matrix4x4(art.uLength.x, 0, 0, art.corner(0, 1, 0).x,
                                     art.uLength.y, 1, 0, art.corner(0, 1, 0).y,
                                     0, 0, 1, 0,
                                     0, 0, 0, 1)
            }

            // MOON / DROP, stacked, as on the device.
            Column {
                x: 18
                y: 14
                spacing: 3
                Text {
                    text: "MOON"
                    color: "#5E636C"
                    font.family: "Segoe UI Variable Text"
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.6
                }
                Text {
                    text: "DROP"
                    color: "#5E636C"
                    font.family: "Segoe UI Variable Text"
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.6
                }
            }

            Rectangle {
                x: 62
                y: 12
                width: 1
                height: 28
                color: "#5E636C"
                opacity: 0.55
            }

            Text {
                x: 72
                y: 11
                text: "DAWN PRO"
                color: "#4F545D"
                font.family: "Segoe UI Variable Text"
                font.pixelSize: 14
                font.weight: Font.Bold
                font.letterSpacing: 1.2
            }

            Column {
                x: 73
                y: 30
                spacing: 1
                Text {
                    text: "DUAL CS43131 DAC"
                    color: "#6A6F78"
                    font.family: "Segoe UI Variable Text"
                    font.pixelSize: 7
                    font.letterSpacing: 0.4
                }
                Text {
                    text: "32BIT/384KHZ & DSD256"
                    color: "#6A6F78"
                    font.family: "Segoe UI Variable Text"
                    font.pixelSize: 7
                    font.letterSpacing: 0.4
                }
            }

            // Status LED, at the USB-C end of the body.
            Rectangle {
                x: 224
                y: 23
                width: 5
                height: 5
                radius: 2.5
                color: art.ledOn ? art.accent : "#6A6F78"

                Rectangle {
                    anchors.centerIn: parent
                    width: 15
                    height: 15
                    radius: 7.5
                    color: art.accent
                    opacity: art.ledOn ? 0.30 : 0
                    Behavior on opacity { NumberAnimation { duration: 220 } }
                }
            }
        }

        // --- end face contents: the two jacks ------------------------------
        Item {
            transform: Matrix4x4 {
                matrix: Qt.matrix4x4(art.uWidth.x, 0, 0, art.origin.x,
                                     art.uWidth.y, 1, 0, art.origin.y,
                                     0, 0, 1, 0,
                                     0, 0, 0, 1)
            }

            // 3.5 mm single-ended, the smaller black socket.
            Item {
                x: 26
                y: 17
                Rectangle {
                    x: -11; y: -11
                    width: 22; height: 22; radius: 11
                    color: "#3C4149"
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.22)
                }
                Rectangle {
                    x: -7.5; y: -7.5
                    width: 15; height: 15; radius: 7.5
                    color: "#111418"
                }
            }

            // 4.4 mm balanced, the larger gold-plated socket.
            Item {
                x: 55
                y: 33
                Rectangle {
                    x: -13.5; y: -13.5
                    width: 27; height: 27; radius: 13.5
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#E8C97A" }
                        GradientStop { position: 1.0; color: "#A98736" }
                    }
                }
                Rectangle {
                    x: -9; y: -9
                    width: 18; height: 18; radius: 9
                    color: "#100F0C"
                }
            }
        }

        // Bright chamfer along the two front top edges.
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeWidth: 1.6
                strokeColor: Qt.rgba(1, 1, 1, 0.5)
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                startX: art.corner(0, 1, 0).x + 10
                startY: art.corner(0, 1, 0).y - 3
                PathLine {
                    x: art.corner(1, 1, 0).x - 10
                    y: art.corner(1, 1, 0).y + 3
                }
            }
        }
    }
}
