import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Effects

ApplicationWindow {
    id: root
    width: 460
    height: 812
    visible: true
    color: "transparent"
    title: "Dawn Pro"
    flags: Qt.Window | Qt.FramelessWindowHint

    property int tabIndex: 0

    // ---- palette ---------------------------------------------------------
    readonly property color bg:        "#0B0D10"
    readonly property color card:      Qt.rgba(1, 1, 1, 0.055)
    readonly property color cardEdge:  Qt.rgba(1, 1, 1, 0.085)
    readonly property color text:      "#F3F6F9"
    readonly property color muted:     "#98A2B0"
    readonly property color faint:     "#6B7482"
    readonly property color accentA:   "#7C5CFF"
    readonly property color accentB:   "#22D3EE"
    readonly property color good:      "#4ADE80"
    readonly property color bad:       "#F87171"
    readonly property string uiFont:   "Segoe UI Variable Text"

    // ---- reusable pieces -------------------------------------------------

    component Card: Rectangle {
        radius: 18
        color: root.card
        border.color: root.cardEdge
        border.width: 1
    }

    component Label: Text {
        color: root.text
        font.family: root.uiFont
        renderType: Text.NativeRendering
    }

    component SectionTitle: Text {
        color: root.faint
        font.family: root.uiFont
        font.pixelSize: 11
        font.letterSpacing: 1.4
        font.weight: Font.DemiBold
        renderType: Text.NativeRendering
    }

    // A pill button that fills with the accent gradient when selected.
    component Pill: Rectangle {
        id: pill
        property string label: ""
        property bool selected: false
        signal clicked()

        implicitHeight: 34
        radius: height / 2
        color: selected ? "transparent" : (hover.hovered ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(1, 1, 1, 0.045))
        border.width: 1
        border.color: selected ? "transparent" : root.cardEdge
        opacity: enabled ? 1 : 0.4

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            visible: pill.selected
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: root.accentA }
                GradientStop { position: 1.0; color: root.accentB }
            }
        }

        Text {
            anchors.centerIn: parent
            text: pill.label
            color: pill.selected ? "#0B0D10" : root.text
            font.family: root.uiFont
            font.pixelSize: 12
            font.weight: pill.selected ? Font.DemiBold : Font.Normal
            renderType: Text.NativeRendering
        }

        HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor; enabled: pill.enabled }
        TapHandler { enabled: pill.enabled; onTapped: pill.clicked() }

        Behavior on color { ColorAnimation { duration: 120 } }
    }

    component Chip: Rectangle {
        property string label: ""
        implicitHeight: 24
        implicitWidth: chipText.implicitWidth + 20
        radius: 12
        color: Qt.rgba(1, 1, 1, 0.06)
        border.width: 1
        border.color: root.cardEdge
        Text {
            id: chipText
            anchors.centerIn: parent
            text: parent.label
            color: root.muted
            font.family: root.uiFont
            font.pixelSize: 11
            font.weight: Font.DemiBold
            renderType: Text.NativeRendering
        }
    }

    // ---- background: the album art, blurred --------------------------------

    Rectangle {
        anchors.fill: parent
        radius: 20
        color: root.bg
        clip: true

        Image {
            id: backdrop
            anchors.fill: parent
            source: controller.artUri
            fillMode: Image.PreserveAspectCrop
            visible: false
            asynchronous: true
        }

        MultiEffect {
            anchors.fill: parent
            source: backdrop
            visible: controller.artUri !== ""
            blurEnabled: true
            blur: 1.0
            blurMax: 64
            saturation: 0.35
            opacity: 0.55
        }

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.043, 0.051, 0.063, 0.72) }
                GradientStop { position: 0.55; color: Qt.rgba(0.043, 0.051, 0.063, 0.93) }
                GradientStop { position: 1.0; color: Qt.rgba(0.043, 0.051, 0.063, 1.0) }
            }
        }

        Rectangle {
            anchors.fill: parent
            radius: 20
            color: "transparent"
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.10)
        }
    }

    // ---- content ---------------------------------------------------------

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 14

        // Title bar ------------------------------------------------------
        Item {
            Layout.fillWidth: true
            implicitHeight: 34

            DragHandler {
                target: null
                onActiveChanged: if (active) root.startSystemMove()
            }

            RowLayout {
                anchors.fill: parent
                spacing: 10

                ColumnLayout {
                    spacing: 0
                    Label {
                        text: "DAWN PRO"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        font.letterSpacing: 2.2
                    }
                    Label {
                        text: "MOONDROP"
                        color: root.faint
                        font.pixelSize: 9
                        font.letterSpacing: 3
                    }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    width: 8; height: 8; radius: 4
                    color: controller.connected ? root.good : root.bad
                    SequentialAnimation on opacity {
                        running: !controller.connected
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.25; duration: 700 }
                        NumberAnimation { to: 1.0; duration: 700 }
                    }
                }
                Label {
                    text: controller.connected ? "Connected" : "Disconnected"
                    color: root.muted
                    font.pixelSize: 11
                }

                Repeater {
                    model: [{ glyph: "–", action: "minimise" }, { glyph: "✕", action: "close" }]
                    delegate: Rectangle {
                        required property var modelData
                        width: 26; height: 26; radius: 13
                        color: btnHover.hovered
                               ? (modelData.action === "close" ? "#E5484D" : Qt.rgba(1, 1, 1, 0.12))
                               : "transparent"
                        Text {
                            anchors.centerIn: parent
                            text: modelData.glyph
                            color: root.muted
                            font.pixelSize: 11
                            renderType: Text.NativeRendering
                        }
                        HoverHandler { id: btnHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler {
                            onTapped: modelData.action === "close" ? root.close() : root.showMinimized()
                        }
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                }
            }
        }

        // Page switch ----------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Repeater {
                model: ["Control", "Device info"]
                delegate: Pill {
                    required property string modelData
                    required property int index
                    implicitWidth: 108
                    label: modelData
                    selected: root.tabIndex === index
                    onClicked: root.tabIndex = index
                }
            }
            Item { Layout.fillWidth: true }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.tabIndex

            // ---- control page ------------------------------------------
            ColumnLayout {
                spacing: 14

                // Now playing ----------------------------------------------------
                Card {
                    Layout.fillWidth: true
                    implicitHeight: nowPlayingRow.implicitHeight + 28

                    RowLayout {
                        id: nowPlayingRow
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 14

                        Item {
                            Layout.alignment: Qt.AlignTop
                            width: 96; height: 96

                            Rectangle {
                                id: artFrame
                                anchors.fill: parent
                                radius: 12
                                color: Qt.rgba(1, 1, 1, 0.05)
                                clip: true

                                Image {
                                    id: art
                                    anchors.fill: parent
                                    source: controller.artUri
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    visible: controller.artUri !== ""
                                }

                                Text {
                                    anchors.centerIn: parent
                                    visible: controller.artUri === ""
                                    text: "♪"
                                    color: root.faint
                                    font.pixelSize: 30
                                }
                            }

                            // Breathing ring while audio is actually playing.
                            Rectangle {
                                anchors.fill: parent
                                radius: 12
                                color: "transparent"
                                border.width: 2
                                border.color: root.accentB
                                opacity: controller.trackPlaying ? 0.20 + controller.level * 0.7 : 0
                                Behavior on opacity { NumberAnimation { duration: 90 } }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 3

                            RowLayout {
                                spacing: 6
                                Rectangle {
                                    width: 6; height: 6; radius: 3
                                    color: controller.trackPlaying ? root.good : root.faint
                                }
                                Label {
                                    text: controller.trackApp !== "" ? controller.trackApp.toUpperCase() : "NOTHING PLAYING"
                                    color: root.faint
                                    font.pixelSize: 10
                                    font.letterSpacing: 1.6
                                    font.weight: Font.DemiBold
                                }
                            }

                            Label {
                                Layout.fillWidth: true
                                text: controller.trackTitle !== "" ? controller.trackTitle : "—"
                                font.pixelSize: 16
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                                maximumLineCount: 2
                                wrapMode: Text.WordWrap
                            }

                            Label {
                                Layout.fillWidth: true
                                text: controller.trackArtist
                                color: root.muted
                                font.pixelSize: 13
                                elide: Text.ElideRight
                                visible: text !== ""
                            }

                            Item { Layout.fillHeight: true }

                            // Output level -----------------------------------------
                            Item {
                                Layout.fillWidth: true
                                implicitHeight: 6

                                Rectangle {
                                    anchors.fill: parent
                                    radius: 3
                                    color: Qt.rgba(1, 1, 1, 0.07)
                                }
                                Rectangle {
                                    height: parent.height
                                    width: parent.width * Math.min(1, controller.level)
                                    radius: 3
                                    gradient: Gradient {
                                        orientation: Gradient.Horizontal
                                        GradientStop { position: 0.0; color: root.accentA }
                                        GradientStop { position: 1.0; color: root.accentB }
                                    }
                                    Behavior on width { NumberAnimation { duration: 55 } }
                                }
                                Rectangle {
                                    width: 2
                                    height: parent.height
                                    radius: 1
                                    color: root.text
                                    opacity: 0.75
                                    x: Math.min(parent.width - width, parent.width * controller.levelPeak)
                                    visible: controller.levelPeak > 0.01
                                }
                            }
                        }
                    }
                }

                // Stream quality -------------------------------------------------
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: controller.formatSummary !== ""

                    Repeater {
                        model: controller.formatSummary.split(" · ")
                        delegate: Chip {
                            required property string modelData
                            label: modelData
                        }
                    }
                    Item { Layout.fillWidth: true }
                }

                // Volume ---------------------------------------------------------
                Card {
                    Layout.fillWidth: true
                    implicitHeight: volumeCol.implicitHeight + 32

                    ColumnLayout {
                        id: volumeCol
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 8

                        SectionTitle { text: "VOLUME" }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            Label {
                                text: controller.volumePercent
                                font.pixelSize: 34
                                font.weight: Font.Light
                            }
                            Label {
                                Layout.alignment: Qt.AlignBottom
                                Layout.bottomMargin: 6
                                text: "%"
                                color: root.muted
                                font.pixelSize: 14
                            }
                            Item { Layout.fillWidth: true }
                        }

                        Slider {
                            id: volumeSlider
                            Layout.fillWidth: true
                            from: 0
                            to: controller.volumeMax
                            stepSize: 1
                            snapMode: Slider.SnapAlways
                            value: controller.volume
                            enabled: controller.connected

                            onMoved: controller.setVolume(Math.round(value))
                            Keys.onLeftPressed: controller.nudgeVolume(-1)
                            Keys.onRightPressed: controller.nudgeVolume(1)

                            background: Rectangle {
                                x: volumeSlider.leftPadding
                                y: volumeSlider.topPadding + volumeSlider.availableHeight / 2 - height / 2
                                width: volumeSlider.availableWidth
                                height: 6
                                radius: 3
                                color: Qt.rgba(1, 1, 1, 0.08)

                                Rectangle {
                                    width: volumeSlider.visualPosition * parent.width
                                    height: parent.height
                                    radius: 3
                                    gradient: Gradient {
                                        orientation: Gradient.Horizontal
                                        GradientStop { position: 0.0; color: root.accentA }
                                        GradientStop { position: 1.0; color: root.accentB }
                                    }
                                }
                            }

                            handle: Rectangle {
                                x: volumeSlider.leftPadding + volumeSlider.visualPosition
                                   * (volumeSlider.availableWidth - width)
                                y: volumeSlider.topPadding + volumeSlider.availableHeight / 2 - height / 2
                                width: 18; height: 18; radius: 9
                                color: "#FFFFFF"
                                scale: volumeSlider.pressed ? 1.15 : 1.0
                                Behavior on scale { NumberAnimation { duration: 90 } }

                                Rectangle {
                                    anchors.centerIn: parent
                                    width: 28; height: 28; radius: 14
                                    color: root.accentB
                                    opacity: volumeSlider.pressed ? 0.25 : 0
                                    Behavior on opacity { NumberAnimation { duration: 120 } }
                                }
                            }

                            WheelHandler {
                                onWheel: (event) => controller.nudgeVolume(event.angleDelta.y > 0 ? 1 : -1)
                            }
                        }
                    }
                }

                // Gain -----------------------------------------------------------
                Card {
                    Layout.fillWidth: true
                    implicitHeight: gainCol.implicitHeight + 32

                    ColumnLayout {
                        id: gainCol
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true
                            SectionTitle { text: "GAIN" }
                            Item { Layout.fillWidth: true }
                            Label {
                                text: controller.gain === 1 ? "More output, more hiss" : "Quieter, lowest noise"
                                color: root.faint
                                font.pixelSize: 11
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Repeater {
                                model: [{ name: "Low", value: 0 }, { name: "High", value: 1 }]
                                delegate: Pill {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    label: modelData.name
                                    selected: controller.gain === modelData.value
                                    enabled: controller.connected
                                    onClicked: controller.setGain(modelData.value)
                                }
                            }
                        }
                    }
                }

                // Filter ---------------------------------------------------------
                Card {
                    Layout.fillWidth: true
                    implicitHeight: filterCol.implicitHeight + 32

                    ColumnLayout {
                        id: filterCol
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        SectionTitle { text: "RECONSTRUCTION FILTER" }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            rowSpacing: 8
                            columnSpacing: 8

                            Repeater {
                                model: [
                                    { name: "Fast · Low latency", value: 0 },
                                    { name: "Fast · Phase comp.", value: 1 },
                                    { name: "Slow · Low latency", value: 2 },
                                    { name: "Slow · Phase comp.", value: 3 },
                                    { name: "Non-oversampling", value: 4 }
                                ]
                                delegate: Pill {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.columnSpan: modelData.value === 4 ? 2 : 1
                                    label: modelData.name
                                    selected: controller.filterIndex === modelData.value
                                    enabled: controller.connected
                                    onClicked: controller.setFilter(modelData.value)
                                }
                            }
                        }
                    }
                }

                // LED ------------------------------------------------------------
                Card {
                    Layout.fillWidth: true
                    implicitHeight: ledCol.implicitHeight + 32

                    ColumnLayout {
                        id: ledCol
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        SectionTitle { text: "LED" }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Repeater {
                                model: [
                                    { name: "On", value: 0 },
                                    { name: "Temporary", value: 1 },
                                    { name: "Off", value: 2 }
                                ]
                                delegate: Pill {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    label: modelData.name
                                    selected: controller.led === modelData.value
                                    enabled: controller.connected
                                    onClicked: controller.setLed(modelData.value)
                                }
                            }
                        }
                    }
                }

                Item { Layout.fillHeight: true }
            }

            // ---- device info page --------------------------------------
            Flickable {
                contentWidth: width
                contentHeight: infoColumn.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                ColumnLayout {
                    id: infoColumn
                    width: parent.width
                    spacing: 14

                    Card {
                        Layout.fillWidth: true
                        implicitHeight: 196

                        DawnProArt {
                            anchors.centerIn: parent
                            width: parent.width - 32
                            height: 172
                            accent: root.accentB
                            ledOn: controller.led === 0
                            visible: controller.productImage === ""
                        }

                        Image {
                            anchors.centerIn: parent
                            width: parent.width - 32
                            height: 172
                            fillMode: Image.PreserveAspectFit
                            source: controller.productImage
                            visible: controller.productImage !== ""
                        }
                    }

                    Repeater {
                        model: controller.infoGroups
                        delegate: Card {
                            id: groupCard
                            required property var modelData
                            Layout.fillWidth: true
                            implicitHeight: groupColumn.implicitHeight + 32

                            ColumnLayout {
                                id: groupColumn
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 9

                                SectionTitle { text: groupCard.modelData.title.toUpperCase() }

                                Label {
                                    Layout.fillWidth: true
                                    Layout.topMargin: -5
                                    text: groupCard.modelData.note
                                    color: root.faint
                                    font.pixelSize: 10
                                    font.italic: true
                                }

                                Repeater {
                                    model: groupCard.modelData.rows
                                    delegate: RowLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        spacing: 14

                                        Label {
                                            text: modelData.label
                                            color: root.muted
                                            font.pixelSize: 11
                                        }
                                        Item { Layout.fillWidth: true }
                                        Label {
                                            // Only hex dumps get the monospace
                                            // treatment; prose values wrap on
                                            // spaces so units stay intact.
                                            readonly property bool isHex:
                                                /^[0-9A-F ]+$/.test(modelData.value)

                                            Layout.maximumWidth: 264
                                            text: modelData.value
                                            font.pixelSize: 11
                                            font.family: isHex ? "Consolas" : root.uiFont
                                            horizontalAlignment: Text.AlignRight
                                            wrapMode: isHex ? Text.WrapAnywhere : Text.WordWrap
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item { implicitHeight: 4 }
                }
            }
        }

        // Footer ---------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Label {
                Layout.fillWidth: true
                text: controller.connected ? controller.rawStatus : controller.message
                color: root.faint
                font.pixelSize: 10
                font.family: "Consolas"
                elide: Text.ElideRight
            }

            Rectangle {
                implicitWidth: retryText.implicitWidth + 22
                implicitHeight: 26
                radius: 13
                visible: !controller.connected
                color: retryHover.hovered ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(1, 1, 1, 0.06)
                border.width: 1
                border.color: root.cardEdge
                Text {
                    id: retryText
                    anchors.centerIn: parent
                    text: "Reconnect"
                    color: root.text
                    font.family: root.uiFont
                    font.pixelSize: 11
                    renderType: Text.NativeRendering
                }
                HoverHandler { id: retryHover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: controller.reconnect() }
            }
        }
    }

    // ---- toast -----------------------------------------------------------

    Rectangle {
        id: toast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 58
        implicitWidth: toastText.implicitWidth + 32
        implicitHeight: 34
        radius: 17
        color: "#151920"
        border.width: 1
        border.color: root.cardEdge
        opacity: 0

        Text {
            id: toastText
            anchors.centerIn: parent
            color: root.text
            font.family: root.uiFont
            font.pixelSize: 12
            renderType: Text.NativeRendering
        }

        SequentialAnimation {
            id: toastAnim
            NumberAnimation { target: toast; property: "opacity"; to: 1; duration: 140 }
            PauseAnimation { duration: 1400 }
            NumberAnimation { target: toast; property: "opacity"; to: 0; duration: 300 }
        }
    }

    Connections {
        target: controller
        function onToast(message) {
            if (message === "")
                return
            toastText.text = message
            toastAnim.restart()
        }
    }

    onClosing: controller.shutdown()
}
