pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 1120
    height: 850
    minimumWidth: 680
    minimumHeight: 600
    visible: true
    title: qsTr("Boolean Logic Workbench")
    color: "#f3f6fb"
    Material.theme: Material.Light
    Material.accent: "#315eaa"

    property var positions: ({})
    property var backend: logic
    property string connectionSource: ""
    property bool wireMode: false
    property real schemeZoom: 1.0

    function fitScheme() {
        var availableWidth = diagramScroll.availableWidth - 32
        var availableHeight = diagramScroll.availableHeight - 32
        if (availableWidth <= 0 || availableHeight <= 0)
            return
        schemeZoom = Math.max(0.15, Math.min(
            1.0,
            availableWidth / backend.schemeWidth,
            availableHeight / backend.schemeHeight
        ))
    }

    function loadCanonicalForm(mode) {
        tabs.currentIndex = 0
        inputMode.currentIndex = mode === "SOP" ? 0 : 1
        expressionInput.text = mode === "SOP" ? backend.sop : backend.pos
        expressionInput.forceActiveFocus()
        expressionInput.cursorPosition = expressionInput.length
    }

    function refreshPositions() {
        var current = ({})
        for (var i = 0; i < backend.schemeNodes.length; i++) {
            var node = backend.schemeNodes[i]
            current[node.id] = {
                x: node.x, y: node.y, width: node.width, height: node.height
            }
        }
        positions = current
        if (typeof wireCanvas !== "undefined")
            wireCanvas.requestPaint()
    }

    function updatePosition(nodeId, x, y) {
        var node = positions[nodeId]
        if (!node)
            return
        var next = Object.assign({}, positions)
        next[nodeId] = {
            x: Math.max(0, Math.min(x, backend.schemeWidth - node.width)),
            y: Math.max(0, Math.min(y, backend.schemeHeight - node.height)),
            width: node.width,
            height: node.height
        }
        positions = next
        wireCanvas.requestPaint()
    }

    Component.onCompleted: refreshPositions()

    header: ColumnLayout {
        spacing: 0
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            color: "#ffffff"
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 22
                anchors.rightMargin: 22
                spacing: 12
                ColumnLayout {
                    spacing: 2
                    Label {
                        text: qsTr("Boolean Logic Workbench")
                        font.pixelSize: 20
                        font.bold: true
                        color: "#17233b"
                    }
                    Label {
                        text: qsTr("Four-variable canonical forms, truth table and gate scheme")
                        font.pixelSize: 12
                        color: "#63718a"
                    }
                }
                Item { Layout.fillWidth: true }
                Button {
                    text: qsTr("Export PDF")
                    enabled: window.backend.hasResult
                    onClicked: pdfDialog.open()
                }
            }
        }
        TabBar {
            id: tabs
            objectName: "mainTabs"
            Layout.fillWidth: true
            onCurrentIndexChanged: {
                if (currentIndex === 2)
                    Qt.callLater(window.fitScheme)
            }
            TabButton { text: qsTr("Canonical forms") }
            TabButton { text: qsTr("Truth table") }
            TabButton { text: qsTr("Gate scheme") }
        }
    }

    StackLayout {
        anchors.fill: parent
        anchors.topMargin: 0
        currentIndex: tabs.currentIndex

        ScrollView {
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AsNeeded
            ColumnLayout {
                width: Math.max(parent.width, 620)
                spacing: 16
                anchors.margins: 22
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 288
                    radius: 12
                    color: "#ffffff"
                    border.color: "#e1e7f0"
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 10
                        Label {
                            text: qsTr("Enter a four-variable canonical form")
                            font.pixelSize: 17
                            font.bold: true
                            color: "#17233b"
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: qsTr("Input form"); color: "#46546c" }
                            ComboBox {
                                id: inputMode
                                model: [
                                    qsTr("Disjunctive (SOP)"),
                                    qsTr("Conjunctive (POS)")
                                ]
                                Layout.preferredWidth: 230
                            }
                            Item { Layout.fillWidth: true }
                        }
                        TextArea {
                            id: expressionInput
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            placeholderText: ""
                            wrapMode: TextEdit.Wrap
                            selectByMouse: true
                            font.family: "monospace"
                            font.pixelSize: 14
                            color: "#17233b"
                            placeholderTextColor: "#75839a"
                            selectionColor: "#b8cff4"
                            selectedTextColor: "#17233b"
                            background: Rectangle {
                                color: "#fbfcff"
                                border.color: "#d8e0ed"
                                radius: 7
                                Text {
                                    anchors.fill: parent
                                    anchors.leftMargin: 12
                                    anchors.topMargin: 10
                                    text: inputMode.currentIndex === 0
                                        ? "Example: A'B'C'D' + A'B + B'D'"
                                        : "Example: ΠP(1, 2, 3)"
                                    color: "#75839a"
                                    font: expressionInput.font
                                    wrapMode: Text.Wrap
                                    verticalAlignment: Text.AlignTop
                                    visible: expressionInput.text.length === 0
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Button {
                                text: qsTr("Calculate")
                                highlighted: true
                                onClicked: window.backend.calculate(
                                    inputMode.currentIndex === 0 ? "SOP" : "POS",
                                    expressionInput.text
                                )
                            }
                            Label {
                                Layout.fillWidth: true
                                text: window.backend.error
                                color: window.backend.error.startsWith("PDF exported") ? "#21824a" : "#bd3b3b"
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }

                Label {
                    text: qsTr("Equivalent canonical forms")
                    font.pixelSize: 17
                    font.bold: true
                    color: "#17233b"
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 190
                    radius: 12
                    color: "#ffffff"
                    border.color: "#e1e7f0"
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        Label {
                            text: qsTr("Disjunctive canonical form (SOP)")
                            font.bold: true
                            color: "#46546c"
                        }
                        TextArea {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 72
                            text: window.backend.hasResult ? window.backend.sop : ""
                            readOnly: true
                            wrapMode: TextEdit.Wrap
                            selectByMouse: true
                            font.family: "monospace"
                            color: "#17233b"
                            selectedTextColor: "#17233b"
                            background: Rectangle { color: "#f8faff"; radius: 6 }
                        }
                        Button {
                            text: qsTr("Edit SOP input")
                            Layout.alignment: Qt.AlignRight
                            enabled: window.backend.hasResult
                            onClicked: window.loadCanonicalForm("SOP")
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 190
                    radius: 12
                    color: "#ffffff"
                    border.color: "#e1e7f0"
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        Label {
                            text: qsTr("Conjunctive canonical form (POS, P-cell notation)")
                            font.bold: true
                            color: "#46546c"
                        }
                        TextArea {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 74
                            text: window.backend.hasResult ? window.backend.pos : ""
                            readOnly: true
                            wrapMode: TextEdit.Wrap
                            selectByMouse: true
                            font.family: "monospace"
                            color: "#17233b"
                            selectedTextColor: "#17233b"
                            background: Rectangle { color: "#f8faff"; radius: 6 }
                        }
                        Button {
                            text: qsTr("Edit POS input")
                            Layout.alignment: Qt.AlignRight
                            enabled: window.backend.hasResult
                            onClicked: window.loadCanonicalForm("POS")
                        }
                    }
                }
                Item { Layout.preferredHeight: 12 }
            }
        }

        ScrollView {
            clip: true
            ColumnLayout {
                width: Math.max(parent.width, 670)
                spacing: 16
                anchors.margins: 22
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 100
                    radius: 12
                    color: "#ffffff"
                    border.color: "#e1e7f0"
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 18
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                Layout.fillWidth: true
                                text: qsTr("Four-variable truth table")
                                font.pixelSize: 19
                                font.bold: true
                                color: "#17233b"
                            }
                            Button {
                                text: qsTr("Clear values")
                                onClicked: window.backend.clearTable()
                            }
                        }
                        Label {
                            text: qsTr("Click a P cell to toggle 0/1. Each value updates the canonical forms and SOP gate scheme.")
                            color: "#63718a"
                            wrapMode: Text.Wrap
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 430
                    radius: 12
                    color: "#ffffff"
                    border.color: "#e1e7f0"
                    Item {
                        id: pGrid
                        anchors.fill: parent
                        anchors.margins: 18
                        Image {
                            id: truthTableImage
                            objectName: "truthTableImage"
                            anchors.fill: parent
                            cache: false
                            fillMode: Image.Stretch
                            source: tableView.imageUrl
                            TapHandler {
                                onTapped: function(eventPoint) {
                                    tableView.toggleCellAt(
                                        eventPoint.position.x,
                                        eventPoint.position.y,
                                        truthTableImage.width,
                                        truthTableImage.height
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 122
                color: "#ffffff"
                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    anchors.topMargin: 8
                    anchors.bottomMargin: 6
                    spacing: 3
                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            Layout.fillWidth: true
                            text: qsTr("Add gates and wire a custom scheme")
                            font.bold: true
                            color: "#17233b"
                        }
                        ComboBox {
                            id: newGateType
                            model: ["AND", "OR", "NOT", "INPUT", "OUTPUT", "0", "1"]
                            Layout.preferredWidth: 100
                        }
                        TextField {
                            id: newGateLabel
                            Layout.preferredWidth: 125
                            placeholderText: qsTr("Optional label")
                            color: "#17233b"
                            placeholderTextColor: "#75839a"
                        }
                        Button {
                            text: qsTr("Add gate")
                            onClicked: {
                                window.backend.addGate(newGateType.currentText, newGateLabel.text)
                                newGateLabel.clear()
                            }
                        }
                        Button {
                            text: window.wireMode ? qsTr("Cancel wire") : qsTr("Connect")
                            highlighted: window.wireMode
                            onClicked: {
                                window.wireMode = !window.wireMode
                                window.connectionSource = ""
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            Layout.fillWidth: true
                            text: window.backend.error
                                ? window.backend.error
                                : window.connectionSource
                                    ? qsTr("Choose destination for %1.").arg(window.connectionSource)
                                    : window.wireMode
                                        ? qsTr("Choose a source gate, then its destination.")
                                        : qsTr("Drag gates to move them; use Fit, zoom, and scrollbars to navigate.")
                            color: window.backend.error ? "#b3261e" : "#46546c"
                            elide: Text.ElideRight
                        }
                        Button {
                            text: qsTr("Fit scheme")
                            onClicked: window.fitScheme()
                        }
                        Button {
                            text: "−"
                            onClicked: window.schemeZoom = Math.max(0.15, window.schemeZoom - 0.1)
                        }
                        Slider {
                            id: zoomSlider
                            from: 0.15
                            to: 1.5
                            stepSize: 0.05
                            value: window.schemeZoom
                            Layout.preferredWidth: 140
                            onMoved: window.schemeZoom = value
                        }
                        Label {
                            Layout.preferredWidth: 48
                            text: Math.round(window.schemeZoom * 100) + "%"
                            color: "#46546c"
                        }
                        Button {
                            text: "+"
                            onClicked: window.schemeZoom = Math.min(1.5, window.schemeZoom + 0.1)
                        }
                    }
                }
            }
            ScrollView {
                id: diagramScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AsNeeded
                ScrollBar.vertical.policy: ScrollBar.AsNeeded
                Item {
                    id: diagramViewport
                    width: Math.ceil(window.backend.schemeWidth * window.schemeZoom)
                    height: Math.ceil(window.backend.schemeHeight * window.schemeZoom)
                    Item {
                        id: diagram
                        width: window.backend.schemeWidth
                        height: window.backend.schemeHeight
                        scale: window.schemeZoom
                        transformOrigin: Item.TopLeft
                    Canvas {
                        id: wireCanvas
                        anchors.fill: parent
                        z: 1
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            ctx.lineCap = "round"
                            for (var i = 0; i < window.backend.connections.length; i++) {
                                var wire = window.backend.connections[i]
                                var from = window.positions[wire.source]
                                var to = window.positions[wire.target]
                                if (!from || !to)
                                    continue
                                var x1 = from.x + from.width
                                var y1 = from.y + wire.sourceOffset
                                var x2 = to.x
                                var y2 = to.y + wire.targetOffset
                                ctx.beginPath()
                                ctx.moveTo(x1, y1)
                                if (wire.wrapSide) {
                                    var wrapDirection = x2 >= x1 ? 1 : -1
                                    var wrapLaunchX = x1 + wrapDirection
                                            * (12 + wire.sourceRouteIndex * 6)
                                    var wrapApproachX = x2 - wrapDirection
                                            * (12 + wire.targetRouteIndex * 6)
                                    ctx.lineTo(wrapLaunchX, y1)
                                    ctx.lineTo(wrapLaunchX, wire.wrapLaneY)
                                    ctx.lineTo(wrapApproachX, wire.wrapLaneY)
                                    ctx.lineTo(wrapApproachX, y2)
                                    ctx.lineTo(x2, y2)
                                } else {
                                    var direction = x2 >= x1 ? 1 : -1
                                    var launchX = x1 + direction
                                            * (12 + wire.sourceRouteIndex * 6)
                                    var approachX = x2 - direction
                                            * (12 + wire.targetRouteIndex * 6)
                                    var channelX = launchX + (approachX - launchX)
                                            * wire.routeChannelFraction
                                    var laneY = (y1 + y2) / 2 + wire.routeLaneOffset
                                    ctx.lineTo(launchX, y1)
                                    ctx.lineTo(channelX, y1)
                                    ctx.lineTo(channelX, laneY)
                                    ctx.lineTo(approachX, laneY)
                                    ctx.lineTo(approachX, y2)
                                    ctx.lineTo(x2, y2)
                                }
                                ctx.strokeStyle = "#ffffff"
                                ctx.lineWidth = 6
                                ctx.stroke()
                                ctx.strokeStyle = wire.color || "#315eaa"
                                ctx.lineWidth = 3
                                ctx.stroke()
                            }
                        }
                    }
                    Repeater {
                        model: window.backend.schemeNodes
                        delegate: Rectangle {
                            id: gate
                            required property var modelData
                            property real currentX: modelData.x
                            property real currentY: modelData.y
                            x: currentX
                            y: currentY
                            width: modelData.width
                            height: modelData.height
                            z: 2
                            radius: 9
                            color: "#f2f6ff"
                            border.color: window.wireMode
                                    && window.connectionSource === modelData.id
                                ? "#e28719" : "#315eaa"
                            border.width: 2

                            Canvas {
                                id: symbol
                                anchors.fill: parent
                                onPaint: {
                                    var ctx = getContext("2d")
                                    ctx.clearRect(0, 0, width, height)
                                    ctx.strokeStyle = "#17233b"
                                    ctx.fillStyle = "#ffffff"
                                    ctx.lineWidth = 2
                                    var iconX = 23
                                    var iconY = 10
                                    for (var i = 0; i < window.backend.connections.length; i++) {
                                        var wire = window.backend.connections[i]
                                        if (wire.target === gate.modelData.id) {
                                            ctx.beginPath()
                                            ctx.strokeStyle = wire.color || "#315eaa"
                                            ctx.moveTo(0, wire.targetOffset)
                                            ctx.lineTo(iconX + 3, wire.targetOffset)
                                            ctx.stroke()
                                        }
                                    }
                                    var outputStartX = gate.modelData.type === "NOT"
                                            ? iconX + 61
                                            : gate.modelData.type === "INPUT"
                                                ? iconX + 54
                                                : gate.modelData.type === "CONSTANT"
                                                    ? iconX + 56
                                                    : iconX + 55
                                    for (var j = 0; j < window.backend.connections.length; j++) {
                                        var outputWire = window.backend.connections[j]
                                        if (outputWire.source !== gate.modelData.id)
                                            continue
                                        ctx.beginPath()
                                        ctx.strokeStyle = outputWire.color || "#315eaa"
                                        ctx.moveTo(outputStartX, outputWire.sourceOffset)
                                        ctx.lineTo(width, outputWire.sourceOffset)
                                        ctx.stroke()
                                    }
                                    ctx.beginPath()
                                    ctx.strokeStyle = "#17233b"
                                    ctx.beginPath()
                                    if (gate.modelData.type === "AND") {
                                        ctx.moveTo(iconX + 3, iconY + 10)
                                        ctx.lineTo(iconX + 28, iconY + 10)
                                        ctx.arc(iconX + 28, iconY + 36, 26,
                                            -Math.PI / 2, Math.PI / 2)
                                        ctx.lineTo(iconX + 3, iconY + 62)
                                        ctx.closePath()
                                        ctx.fill()
                                        ctx.stroke()
                                    } else if (gate.modelData.type === "OR") {
                                        ctx.moveTo(iconX + 3, iconY + 8)
                                        ctx.quadraticCurveTo(iconX + 20, 46,
                                            iconX + 3, iconY + 68)
                                        ctx.quadraticCurveTo(iconX + 36, 68,
                                            iconX + 60, 50)
                                        ctx.quadraticCurveTo(iconX + 36, 32,
                                            iconX + 3, iconY + 8)
                                        ctx.closePath()
                                        ctx.fill()
                                        ctx.stroke()
                                    } else if (gate.modelData.type === "NOT") {
                                        ctx.moveTo(iconX + 6, iconY + 14)
                                        ctx.lineTo(iconX + 49, 50)
                                        ctx.lineTo(iconX + 6, iconY + 58)
                                        ctx.closePath()
                                        ctx.fill()
                                        ctx.stroke()
                                        ctx.beginPath()
                                        ctx.arc(iconX + 55, 50, 5, 0, 2 * Math.PI)
                                        ctx.fill()
                                        ctx.stroke()
                                    } else if (gate.modelData.type === "INPUT") {
                                        ctx.arc(iconX + 30, 49, 21, 0, 2 * Math.PI)
                                        ctx.fill()
                                        ctx.stroke()
                                    } else {
                                        ctx.rect(iconX + 4, iconY + 12, 52, 50)
                                        ctx.fill()
                                        ctx.stroke()
                                        if (gate.modelData.type === "CONSTANT") {
                                            ctx.fillStyle = "#17233b"
                                            ctx.font = "bold 22px sans-serif"
                                            ctx.textAlign = "center"
                                            ctx.textBaseline = "middle"
                                            ctx.fillText(gate.modelData.label,
                                                iconX + 30, 47)
                                        }
                                    }
                                }
                            }
                            Label {
                                anchors.horizontalCenter: parent.horizontalCenter
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 3
                                width: parent.width - 8
                                text: gate.modelData.label
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                                font.pixelSize: 10
                                font.bold: true
                                color: "#26354f"
                            }
                            TapHandler {
                                onTapped: {
                                    if (!window.wireMode)
                                        return
                                    if (!window.connectionSource) {
                                        window.connectionSource = gate.modelData.id
                                    } else {
                                        window.backend.connectNodes(
                                            window.connectionSource, gate.modelData.id
                                        )
                                        window.connectionSource = ""
                                        window.wireMode = false
                                    }
                                }
                            }
                            MouseArea {
                                anchors.fill: parent
                                acceptedButtons: Qt.NoButton
                                cursorShape: Qt.OpenHandCursor
                            }
                            DragHandler {
                                id: dragHandler
                                target: null
                                property point origin
                                onActiveChanged: {
                                    if (active) {
                                        origin = Qt.point(gate.currentX, gate.currentY)
                                    } else {
                                        window.backend.moveNode(gate.modelData.id, gate.currentX, gate.currentY)
                                    }
                                }
                                onTranslationChanged: {
                                    if (!active)
                                        return
                                    var nextX = origin.x + translation.x
                                    var nextY = origin.y + translation.y
                                    gate.currentX = Math.max(0, Math.min(
                                        nextX, window.backend.schemeWidth - gate.width
                                    ))
                                    gate.currentY = Math.max(0, Math.min(
                                        nextY, window.backend.schemeHeight - gate.height
                                    ))
                                    window.updatePosition(
                                        gate.modelData.id, gate.currentX, gate.currentY
                                    )
                                }
                            }
                        }
                    }
                    Label {
                        anchors.left: parent.left
                        anchors.bottom: parent.bottom
                        anchors.margins: 12
                        text: window.backend.error
                            ? window.backend.error
                            : window.backend.hasResult
                                ? qsTr("Generated from the current function · drag gates or add custom logic")
                                : qsTr("Add a gate or calculate a canonical form to build the scheme.")
                        color: window.backend.error ? "#b3261e" : "#46546c"
                        font.pixelSize: 12
                        z: 3
                    }
                    }
                }
            }
        }

    }

    FileDialog {
        id: pdfDialog
        title: qsTr("Export Boolean logic as PDF")
        fileMode: FileDialog.SaveFile
        nameFilters: ["PDF files (*.pdf)"]
        defaultSuffix: "pdf"
        onAccepted: window.backend.exportPdf(selectedFile.toString())
    }

    Connections {
        target: window.backend
        function onSchemeChanged() {
            window.refreshPositions()
        }
    }
}
