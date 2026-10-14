export default function EventLog({events}) {
    return (
        <div className="border p-4 rounded-xl">
            <h2>EventLog</h2>
            <pre>{JSON.stringify(events, null, 2)}</pre>
        </div>
    )
}