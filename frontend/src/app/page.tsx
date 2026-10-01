import BackendStatus from "@/components/BackendStatus";

export default function Home() {
  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "2rem 16px" }}>
      <h1>AI Nutrition Assistant</h1>
      <p>General food, nutrition and food-safety information from official guidance. Not medical advice.</p>
      <BackendStatus />
    </main>
  );
}
