import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Header } from "@/components/Header";
import { ScrollReveal } from "@/components/ScrollReveal";
import { ShineOverlay } from "@/components/ShineOverlay";
import { DollarSign, Users, FileText, BookOpen, Calendar, CheckCircle, GraduationCap, Award, TrendingUp, Shield, Facebook, Twitter, Linkedin, Mail } from "lucide-react";

const FEATURES = [
    {
        icon: Users,
        color: "blue",
        title: "Student & Teacher Management",
        description: "Comprehensive profiles, role-based access, and automated enrollment processes.",
    },
    {
        icon: FileText,
        color: "green",
        title: "Assignments & Grading",
        description: "Create, distribute, and grade assignments with automated workflows and feedback.",
    },
    {
        icon: Calendar,
        color: "teal",
        title: "Attendance Tracking",
        description: "Real-time attendance monitoring with automated alerts and detailed reports.",
    },
    {
        icon: DollarSign,
        color: "orange",
        title: "Fee Management",
        description: "Automated billing, fee collection, invoice generation, and financial reporting.",
    },
    {
        icon: Shield,
        color: "emerald",
        title: "Secure Online Payments",
        description: "PCI-compliant payment processing with multiple gateway integrations.",
    },
    {
        icon: TrendingUp,
        color: "indigo",
        title: "Analytics & Reports",
        description: "Insights into academic performance, attendance trends, and financial health.",
    },
] as const;

const COLOR_CLASSES: Record<string, string> = {
    blue: "bg-blue-100 text-blue-600 group-hover:bg-blue-600 group-hover:text-white",
    green: "bg-green-100 text-green-600 group-hover:bg-green-600 group-hover:text-white",
    teal: "bg-teal-100 text-teal-600 group-hover:bg-teal-600 group-hover:text-white",
    orange: "bg-orange-100 text-orange-600 group-hover:bg-orange-600 group-hover:text-white",
    emerald: "bg-emerald-100 text-emerald-600 group-hover:bg-emerald-600 group-hover:text-white",
    indigo: "bg-indigo-100 text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white",
};

const STEPS = [
    {
        number: 1,
        gradient: "from-blue-500 to-blue-600",
        title: "Sign Up",
        description: "Create your institution account in under 2 minutes. No credit card required.",
    },
    {
        number: 2,
        gradient: "from-teal-500 to-teal-600",
        title: "Configure",
        description: "Set up your classes, add staff and students, and customize your workflow.",
    },
    {
        number: 3,
        gradient: "from-green-500 to-green-600",
        title: "Launch",
        description: "Go live and start managing your institution with ease and efficiency.",
    },
] as const;

const TESTIMONIALS = [
    {
        quote: "Edu Sekai transformed how we manage our school. The attendance and fee management features alone saved us countless hours every week.",
        name: "Dr. Sarah Johnson",
        role: "Principal, Lincoln High School",
        gradient: "from-blue-500 to-blue-600",
    },
    {
        quote: "The multi-tenant architecture is perfect for our college network. We manage 5 campuses effortlessly from one platform.",
        name: "Prof. Michael Chen",
        role: "Dean, Metro University",
        gradient: "from-teal-500 to-teal-600",
    },
    {
        quote: "Parents love the real-time updates and the secure payment system. Our collection efficiency improved by 40%!",
        name: "Ms. Priya Sharma",
        role: "Administrator, Bright Future School",
        gradient: "from-green-500 to-green-600",
    },
] as const;

export default function LandingPage() {
    return (
        <div className="flex flex-col min-h-screen">
            <Header />

            <main className="flex-1">
                {/* Hero Section */}
                <section className="w-full py-20 md:py-32 lg:py-40 bg-gradient-to-br from-blue-50 via-teal-50 to-green-50 relative overflow-hidden">
                    {/* Ambient animated gradient blobs */}
                    <div className="absolute inset-0 overflow-hidden pointer-events-none">
                        <div className="absolute -top-24 -left-24 w-96 h-96 bg-blue-300/30 rounded-full blur-3xl animate-blob" />
                        <div className="absolute top-1/3 -right-24 w-96 h-96 bg-teal-300/30 rounded-full blur-3xl animate-blob animation-delay-2000" />
                        <div className="absolute -bottom-24 left-1/3 w-96 h-96 bg-green-300/30 rounded-full blur-3xl animate-blob animation-delay-4000" />
                    </div>

                    <div className="container px-4 md:px-6 relative z-10">
                        <div className="flex flex-col items-center space-y-6 text-center">
                            <div className="space-y-4">
                                <h1 className="animate-in fade-in slide-in-from-bottom-6 duration-700 fill-mode-both text-4xl font-bold tracking-tighter sm:text-5xl md:text-6xl lg:text-7xl/none text-slate-900">
                                    Transform Education Management
                                </h1>
                                <p className="animate-in fade-in slide-in-from-bottom-6 duration-700 delay-150 fill-mode-both mx-auto max-w-[700px] text-lg md:text-xl text-slate-600">
                                    Cloud-based multi-tenant platform for schools, colleges, and universities. Manage students, teachers, assignments, attendance, fees, and payments—all in one place.
                                </p>
                            </div>
                            <div className="animate-in fade-in slide-in-from-bottom-6 duration-700 delay-300 fill-mode-both flex flex-wrap gap-4 justify-center">
                                <Link href="/get-started">
                                    <Button size="lg" className="group relative overflow-hidden text-lg px-8 py-6 bg-blue-600 hover:bg-blue-700 hover:scale-105 active:scale-100 transition-all duration-300 ease-out shadow-lg shadow-blue-600/20 hover:shadow-xl hover:shadow-blue-600/40">
                                        <ShineOverlay />
                                        <span className="relative">Start Free Trial</span>
                                    </Button>
                                </Link>
                                <Link href="#features">
                                    <Button size="lg" variant="outline" className="group relative overflow-hidden text-lg px-8 py-6 border-2 border-blue-600 text-blue-600 bg-transparent hover:text-white hover:border-transparent hover:bg-gradient-to-r hover:from-blue-600 hover:to-teal-600 hover:shadow-xl hover:shadow-blue-600/30 hover:scale-105 active:scale-100 transition-all duration-300 ease-out">
                                        <ShineOverlay />
                                        <span className="relative">Watch Demo</span>
                                    </Button>
                                </Link>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Features Section */}
                <section id="features" className="w-full py-20 md:py-28 bg-gradient-to-b from-white via-blue-50/40 to-white relative overflow-hidden">
                    <div className="absolute -top-32 -right-32 w-80 h-80 bg-blue-200/20 rounded-full blur-3xl pointer-events-none" />
                    <div className="container px-4 md:px-6 relative z-10">
                        <ScrollReveal className="text-center mb-12">
                            <h2 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl mb-4 bg-gradient-to-r from-blue-600 to-teal-600 bg-clip-text text-transparent">
                                Powerful Features for Modern Education
                            </h2>
                            <p className="text-slate-600 max-w-2xl mx-auto">
                                Everything you need to manage your institution efficiently and effectively
                            </p>
                        </ScrollReveal>
                        <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-3">
                            {FEATURES.map((feature, i) => (
                                <ScrollReveal key={feature.title} delay={i * 100}>
                                    <div className="group h-full flex flex-col items-start space-y-3 p-6 bg-white rounded-xl shadow-md hover:shadow-2xl hover:shadow-blue-900/10 transition-all duration-300 ease-out hover:-translate-y-2 hover:scale-[1.02] border border-slate-200 hover:border-blue-300">
                                        <div className={`p-3 rounded-lg transition-all duration-300 ease-out group-hover:scale-110 group-hover:-rotate-6 ${COLOR_CLASSES[feature.color]}`}>
                                            <feature.icon className="h-7 w-7" />
                                        </div>
                                        <h3 className="text-xl font-bold text-slate-900">{feature.title}</h3>
                                        <p className="text-slate-600">{feature.description}</p>
                                    </div>
                                </ScrollReveal>
                            ))}
                        </div>
                    </div>
                </section>

                {/* How It Works Section */}
                <section id="how-it-works" className="w-full py-20 md:py-28 bg-gradient-to-b from-green-50/60 via-slate-50 to-white">
                    <div className="container px-4 md:px-6">
                        <ScrollReveal className="text-center mb-16">
                            <h2 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl mb-4 bg-gradient-to-r from-blue-600 to-teal-600 bg-clip-text text-transparent">
                                How It Works
                            </h2>
                            <p className="text-slate-600 max-w-2xl mx-auto">
                                Get started in minutes with our simple three-step process
                            </p>
                        </ScrollReveal>
                        <div className="relative grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-8 max-w-5xl mx-auto">
                            <div className="hidden md:block absolute top-10 left-[16.5%] right-[16.5%] h-0.5 bg-gradient-to-r from-blue-200 via-teal-200 to-green-200" />
                            {STEPS.map((step, i) => (
                                <ScrollReveal key={step.number} delay={i * 150} className="relative flex flex-col items-center text-center space-y-4">
                                    <div className={`w-20 h-20 rounded-full bg-gradient-to-br ${step.gradient} text-white flex items-center justify-center text-3xl font-bold shadow-lg transition-all duration-300 ease-out hover:scale-110 hover:shadow-xl hover:shadow-blue-900/20 ring-4 ring-transparent hover:ring-blue-100`}>
                                        {step.number}
                                    </div>
                                    <h3 className="text-2xl font-bold text-slate-900">{step.title}</h3>
                                    <p className="text-slate-600">{step.description}</p>
                                </ScrollReveal>
                            ))}
                        </div>
                    </div>
                </section>

                {/* Testimonials Section */}
                <section id="testimonials" className="w-full py-20 md:py-28 bg-gradient-to-b from-white via-teal-50/40 to-white relative overflow-hidden">
                    <div className="absolute -bottom-32 -left-32 w-80 h-80 bg-teal-200/20 rounded-full blur-3xl pointer-events-none" />
                    <div className="container px-4 md:px-6 relative z-10">
                        <ScrollReveal className="text-center mb-16">
                            <h2 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl mb-4 bg-gradient-to-r from-blue-600 to-teal-600 bg-clip-text text-transparent">
                                Trusted by Educators Worldwide
                            </h2>
                            <p className="text-slate-600 max-w-2xl mx-auto">
                                See what institutions are saying about Edu Sekai
                            </p>
                        </ScrollReveal>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                            {TESTIMONIALS.map((t, i) => (
                                <ScrollReveal key={t.name} delay={i * 100}>
                                    <div className="h-full bg-white p-8 rounded-xl shadow-md border border-slate-200 transition-all duration-300 ease-out hover:shadow-2xl hover:shadow-teal-900/10 hover:-translate-y-1.5 hover:scale-[1.015] hover:border-teal-200">
                                        <div className="flex items-center mb-4">
                                            {[...Array(5)].map((_, j) => (
                                                <Award key={j} className="h-5 w-5 text-yellow-400 fill-yellow-400" />
                                            ))}
                                        </div>
                                        <p className="text-slate-600 mb-6 italic">&ldquo;{t.quote}&rdquo;</p>
                                        <div className="flex items-center gap-3">
                                            <div className={`w-12 h-12 rounded-full bg-gradient-to-br ${t.gradient}`}></div>
                                            <div>
                                                <p className="font-bold text-slate-900">{t.name}</p>
                                                <p className="text-sm text-slate-500">{t.role}</p>
                                            </div>
                                        </div>
                                    </div>
                                </ScrollReveal>
                            ))}
                        </div>
                    </div>
                </section>

                {/* Pricing Section */}
                <section id="pricing" className="w-full py-20 md:py-28 bg-gradient-to-b from-blue-50/60 via-slate-50 to-white">
                    <div className="container px-4 md:px-6">
                        <ScrollReveal className="text-center mb-16">
                            <h2 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl mb-4 bg-gradient-to-r from-blue-600 to-teal-600 bg-clip-text text-transparent">
                                Simple, Transparent Pricing
                            </h2>
                            <p className="text-slate-600 max-w-2xl mx-auto">
                                Choose the plan that fits your institution&apos;s needs
                            </p>
                        </ScrollReveal>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto md:items-center">
                            <ScrollReveal delay={0}>
                                <div className="h-full bg-white p-8 rounded-xl shadow-md border-2 border-slate-200 hover:border-blue-500 hover:shadow-xl hover:shadow-blue-900/10 transition-all duration-300 ease-out hover:-translate-y-1.5">
                                    <h3 className="text-2xl font-bold mb-2 text-slate-900">Starter</h3>
                                    <p className="text-slate-600 mb-6">Perfect for small schools</p>
                                    <div className="mb-6">
                                        <span className="text-4xl font-bold text-slate-900">$49</span>
                                        <span className="text-slate-600">/month</span>
                                    </div>
                                    <ul className="space-y-3 mb-8">
                                        <li className="flex items-center gap-2">
                                            <CheckCircle className="h-5 w-5 text-green-500" />
                                            <span className="text-slate-700">Up to 200 students</span>
                                        </li>
                                        <li className="flex items-center gap-2">
                                            <CheckCircle className="h-5 w-5 text-green-500" />
                                            <span className="text-slate-700">Basic features</span>
                                        </li>
                                        <li className="flex items-center gap-2">
                                            <CheckCircle className="h-5 w-5 text-green-500" />
                                            <span className="text-slate-700">Email support</span>
                                        </li>
                                        <li className="flex items-center gap-2">
                                            <CheckCircle className="h-5 w-5 text-green-500" />
                                            <span className="text-slate-700">5GB storage</span>
                                        </li>
                                    </ul>
                                    <Button className="w-full bg-slate-100 text-slate-900 hover:bg-slate-900 hover:text-white transition-all duration-300 ease-out hover:scale-[1.03]">Choose Plan</Button>
                                </div>
                            </ScrollReveal>
                            <ScrollReveal delay={150}>
                                <div className="relative">
                                    <div className="absolute -inset-1 rounded-xl bg-gradient-to-br from-blue-600 to-teal-600 opacity-75 blur-lg animate-glow-pulse" />
                                    <div className="relative bg-gradient-to-br from-blue-600 to-teal-600 p-8 rounded-xl shadow-2xl border-2 border-blue-600 md:scale-105 text-white transition-all duration-300 ease-out hover:scale-[1.08] hover:shadow-blue-900/30">
                                        <div className="bg-white text-blue-600 px-3 py-1 rounded-full text-sm font-bold inline-block mb-4">Most Popular</div>
                                        <h3 className="text-2xl font-bold mb-2">Professional</h3>
                                        <p className="text-blue-100 mb-6">For growing institutions</p>
                                        <div className="mb-6">
                                            <span className="text-4xl font-bold">$149</span>
                                            <span className="text-blue-100">/month</span>
                                        </div>
                                        <ul className="space-y-3 mb-8">
                                            <li className="flex items-center gap-2">
                                                <CheckCircle className="h-5 w-5 text-white" />
                                                <span>Up to 1000 students</span>
                                            </li>
                                            <li className="flex items-center gap-2">
                                                <CheckCircle className="h-5 w-5 text-white" />
                                                <span>All features</span>
                                            </li>
                                            <li className="flex items-center gap-2">
                                                <CheckCircle className="h-5 w-5 text-white" />
                                                <span>Priority support</span>
                                            </li>
                                            <li className="flex items-center gap-2">
                                                <CheckCircle className="h-5 w-5 text-white" />
                                                <span>50GB storage</span>
                                            </li>
                                            <li className="flex items-center gap-2">
                                                <CheckCircle className="h-5 w-5 text-white" />
                                                <span>Custom branding</span>
                                            </li>
                                        </ul>
                                        <Button className="group relative overflow-hidden w-full bg-white text-blue-600 hover:bg-blue-50 transition-all duration-300 ease-out hover:scale-[1.03]" size="lg">
                                            <ShineOverlay />
                                            <span className="relative">Choose Plan</span>
                                        </Button>
                                    </div>
                                </div>
                            </ScrollReveal>
                            <ScrollReveal delay={300}>
                                <div className="h-full bg-white p-8 rounded-xl shadow-md border-2 border-slate-200 hover:border-blue-500 hover:shadow-xl hover:shadow-blue-900/10 transition-all duration-300 ease-out hover:-translate-y-1.5">
                                    <h3 className="text-2xl font-bold mb-2 text-slate-900">Enterprise</h3>
                                    <p className="text-slate-600 mb-6">For large universities</p>
                                    <div className="mb-6">
                                        <span className="text-4xl font-bold text-slate-900">Custom</span>
                                    </div>
                                    <ul className="space-y-3 mb-8">
                                        <li className="flex items-center gap-2">
                                            <CheckCircle className="h-5 w-5 text-green-500" />
                                            <span className="text-slate-700">Unlimited students</span>
                                        </li>
                                        <li className="flex items-center gap-2">
                                            <CheckCircle className="h-5 w-5 text-green-500" />
                                            <span className="text-slate-700">All features</span>
                                        </li>
                                        <li className="flex items-center gap-2">
                                            <CheckCircle className="h-5 w-5 text-green-500" />
                                            <span className="text-slate-700">24/7 dedicated support</span>
                                        </li>
                                        <li className="flex items-center gap-2">
                                            <CheckCircle className="h-5 w-5 text-green-500" />
                                            <span className="text-slate-700">Unlimited storage</span>
                                        </li>
                                        <li className="flex items-center gap-2">
                                            <CheckCircle className="h-5 w-5 text-green-500" />
                                            <span className="text-slate-700">Custom integrations</span>
                                        </li>
                                    </ul>
                                    <Button className="w-full bg-slate-100 text-slate-900 hover:bg-slate-900 hover:text-white transition-all duration-300 ease-out hover:scale-[1.03]">Contact Sales</Button>
                                </div>
                            </ScrollReveal>
                        </div>
                    </div>
                </section>

                {/* CTA Section */}
                <section className="w-full py-20 md:py-28 bg-gradient-to-br from-blue-600 via-teal-600 to-blue-600 animate-gradient text-white relative overflow-hidden">
                    <div className="container px-4 md:px-6 relative z-10">
                        <ScrollReveal className="flex flex-col items-center text-center space-y-6">
                            <h2 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl max-w-3xl">
                                Ready to Transform Your Institution?
                            </h2>
                            <p className="text-lg md:text-xl text-blue-100 max-w-2xl">
                                Join thousands of schools, colleges, and universities already using Edu Sekai
                            </p>
                            <div className="flex flex-wrap gap-4 justify-center">
                                <Link href="/get-started">
                                    <Button size="lg" className="group relative overflow-hidden text-lg px-10 py-6 bg-white text-blue-600 hover:bg-blue-50 hover:scale-105 active:scale-100 transition-all duration-300 ease-out shadow-xl hover:shadow-2xl">
                                        <ShineOverlay />
                                        <span className="relative">Start Free 30-Day Trial</span>
                                    </Button>
                                </Link>
                                <Link href="/contact">
                                    <Button size="lg" variant="outline" className="group relative overflow-hidden text-lg px-10 py-6 text-white border-white hover:bg-white hover:text-blue-600 hover:scale-105 active:scale-100 transition-all duration-300 ease-out bg-transparent">
                                        <ShineOverlay />
                                        <span className="relative">Schedule a Demo</span>
                                    </Button>
                                </Link>
                            </div>
                        </ScrollReveal>
                    </div>
                </section>
            </main>

            {/* Footer */}
            <footer className="bg-slate-900 text-white py-12">
                <div className="container px-4 md:px-6">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
                        <div>
                            <div className="flex items-center gap-2 mb-4">
                                <GraduationCap className="h-8 w-8 text-blue-400" />
                                <span className="font-bold text-xl">Edu Sekai</span>
                            </div>
                            <p className="text-slate-400 text-sm">
                                Transforming education management with cloud-based solutions.
                            </p>
                        </div>
                        <div>
                            <h4 className="font-bold mb-4">Product</h4>
                            <ul className="space-y-2 text-sm text-slate-400">
                                <li><Link href="#features" className="hover:text-white transition-colors">Features</Link></li>
                                <li><Link href="#pricing" className="hover:text-white transition-colors">Pricing</Link></li>
                                <li><Link href="#" className="hover:text-white transition-colors">Security</Link></li>
                                <li><Link href="#" className="hover:text-white transition-colors">Integrations</Link></li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="font-bold mb-4">Company</h4>
                            <ul className="space-y-2 text-sm text-slate-400">
                                <li><Link href="#" className="hover:text-white transition-colors">About Us</Link></li>
                                <li><Link href="#" className="hover:text-white transition-colors">Careers</Link></li>
                                <li><Link href="#" className="hover:text-white transition-colors">Blog</Link></li>
                                <li><Link href="#" className="hover:text-white transition-colors">Contact</Link></li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="font-bold mb-4">Connect</h4>
                            <div className="flex gap-4 mb-4">
                                <Link href="#" className="hover:text-blue-400 hover:-translate-y-0.5 transition-all inline-block">
                                    <Facebook className="h-6 w-6" />
                                </Link>
                                <Link href="#" className="hover:text-blue-400 hover:-translate-y-0.5 transition-all inline-block">
                                    <Twitter className="h-6 w-6" />
                                </Link>
                                <Link href="#" className="hover:text-blue-400 hover:-translate-y-0.5 transition-all inline-block">
                                    <Linkedin className="h-6 w-6" />
                                </Link>
                                <Link href="#" className="hover:text-blue-400 hover:-translate-y-0.5 transition-all inline-block">
                                    <Mail className="h-6 w-6" />
                                </Link>
                            </div>
                            <p className="text-sm text-slate-400">support@edusekai.com</p>
                        </div>
                    </div>
                    <div className="border-t border-slate-800 pt-8 flex flex-col sm:flex-row justify-between items-center text-sm text-slate-400">
                        <p>© 2024 Edu Sekai. All rights reserved.</p>
                        <div className="flex gap-6 mt-4 sm:mt-0">
                            <Link href="#" className="hover:text-white transition-colors">Privacy Policy</Link>
                            <Link href="#" className="hover:text-white transition-colors">Terms of Service</Link>
                            <Link href="#" className="hover:text-white transition-colors">Cookie Policy</Link>
                        </div>
                    </div>
                </div>
            </footer>
        </div>
    );
}
