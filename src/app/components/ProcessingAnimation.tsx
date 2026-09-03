import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Shield, Activity, FileText, Network, CheckCircle } from "lucide-react";

interface ProcessingAnimationProps {
  onComplete?: () => void;
}

export function ProcessingAnimation({ onComplete }: ProcessingAnimationProps) {
  const [currentStep, setCurrentStep] = useState(0);
  
  const steps = [
    { 
      icon: Activity, 
      label: "Anomaly Detection", 
      description: "Running Isolation Forest algorithm...",
      color: "text-blue-600"
    },
    { 
      icon: Shield, 
      label: "Evidence Gathering", 
      description: "Analyzing velocity & structuring patterns...",
      color: "text-purple-600"
    },
    { 
      icon: FileText, 
      label: "Risk Scoring", 
      description: "Mapping to FATF typologies...",
      color: "text-orange-600"
    },
    { 
      icon: Network, 
      label: "Network Analysis", 
      description: "Computing PageRank & SCC...",
      color: "text-green-600"
    },
    { 
      icon: CheckCircle, 
      label: "STR Generation", 
      description: "Generating compliance report...",
      color: "text-red-600"
    },
  ];
  
  useEffect(() => {
    if (currentStep < steps.length) {
      const timer = setTimeout(() => {
        setCurrentStep(currentStep + 1);
      }, 1500);
      return () => clearTimeout(timer);
    } else if (onComplete) {
      onComplete();
    }
  }, [currentStep, onComplete, steps.length]);
  
  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50">
      <motion.div 
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="bg-white rounded-xl shadow-2xl p-8 max-w-md w-full mx-4"
      >
        <div className="text-center mb-6">
          <Shield className="w-12 h-12 text-blue-600 mx-auto mb-3" />
          <h3 className="text-xl font-bold text-slate-900">Processing Case</h3>
          <p className="text-sm text-slate-600">Multi-agent pipeline in progress...</p>
        </div>
        
        <div className="space-y-4">
          {steps.map((step, idx) => {
            const Icon = step.icon;
            const isActive = idx === currentStep;
            const isComplete = idx < currentStep;
            
            return (
              <motion.div
                key={idx}
                initial={{ x: -20, opacity: 0 }}
                animate={{ 
                  x: 0, 
                  opacity: idx <= currentStep ? 1 : 0.3,
                  scale: isActive ? 1.05 : 1
                }}
                transition={{ delay: idx * 0.1 }}
                className={`flex items-center gap-3 p-3 rounded-lg border-2 transition-all ${
                  isActive 
                    ? 'border-blue-500 bg-blue-50 shadow-md' 
                    : isComplete
                    ? 'border-green-500 bg-green-50'
                    : 'border-slate-200 bg-slate-50'
                }`}
              >
                <div className={`${
                  isComplete ? 'bg-green-600' : isActive ? 'bg-blue-600' : 'bg-slate-300'
                } p-2 rounded-lg`}>
                  <Icon className="w-5 h-5 text-white" />
                </div>
                
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-900">{step.label}</p>
                  {isActive && (
                    <motion.p 
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="text-xs text-slate-600"
                    >
                      {step.description}
                    </motion.p>
                  )}
                </div>
                
                {isComplete && (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                  >
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  </motion.div>
                )}
                
                {isActive && (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  >
                    <Activity className="w-5 h-5 text-blue-600" />
                  </motion.div>
                )}
              </motion.div>
            );
          })}
        </div>
        
        <div className="mt-6">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-slate-600">Progress</span>
            <span className="font-bold text-slate-900">
              {Math.round((currentStep / steps.length) * 100)}%
            </span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-2">
            <motion.div 
              className="bg-blue-600 h-2 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${(currentStep / steps.length) * 100}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>
        
        {currentStep >= steps.length && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg text-center"
          >
            <p className="text-sm font-medium text-green-900">
              ✓ Processing complete in 7.3s
            </p>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
