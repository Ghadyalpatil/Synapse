export default function StatusTimeline({events}) {
    return (
        <div className="border p-4 rounded-xl">
            <h2>StatusTimeline</h2>
            {events.map((event, index) => (
                <div key={index}>
                    <div>{event.type}</div>
                    <div>{event.packet_id}</div>
                </div>
            ))}
        </div>
    )
}